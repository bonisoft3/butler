import { Client, LocalAuth, Message, NoAuth } from 'whatsapp-web.js';
import qrcode from 'qrcode-terminal';
import logger from './logger';
import fs from 'fs';
import path from 'path';
import axios from 'axios';
import qrcodepng from 'qrcode';
import { createCanvas } from 'canvas';
import express, { Request, Response } from 'express';
import { WhatsAppService } from './whatsapp-service';

const QUERY_PREFIX = process.env.QUERY_PREFIX || '🤖 *butler:*';

// Configuration interface
export interface WhatsAppConfig {
  authDataPath?: string;
  authStrategy?: 'local' | 'none';
  dockerContainer?: boolean;
  mediaStoragePath?: string;
}

interface WebhookConfig {
  url: string;
  authToken?: string;
  filters?: {
    allowedNumbers?: string[];
    allowPrivate?: boolean;
    allowGroups?: boolean;
    allowSelfChat?: boolean;
  };
}

function loadWebhookConfig(dataPath: string): WebhookConfig | undefined {
  const webhookConfigPath = path.join(dataPath, 'webhook.json');
  if (!fs.existsSync(webhookConfigPath)) {
    return undefined;
  }
  return JSON.parse(fs.readFileSync(webhookConfigPath, 'utf8'));
}

function shouldSkipMessageByFilters(
  isGroup: boolean,
  isSelfChat: boolean,
  contactNumber: string,
  filters?: WebhookConfig['filters']
): boolean {
  if (!filters) return false;

  if (isGroup && filters.allowGroups === false) {
    logger.debug('Skipping: message from group and allowGroups=false');
    return true;
  }

  if (!isGroup && !isSelfChat && filters.allowPrivate === false) {
    logger.debug('Skipping: message from private chat and allowPrivate=false');
    return true;
  }

  if (isSelfChat && filters.allowSelfChat === false) {
    logger.debug('Skipping: message from self chat and allowSelfChat=false');
    return true;
  }

  if (
    filters.allowedNumbers?.length &&
    !filters.allowedNumbers.includes(contactNumber)
  ) {
    logger.debug(`Skipping: contact ${contactNumber} not in allowedNumbers`);
    return true;
  }

  return false;
}

export function createWhatsAppClient(config: WhatsAppConfig = {}): Client {
  const authDataPath = config.authDataPath || '.wwebjs_auth';
  const mediaStoragePath = config.mediaStoragePath || path.join(authDataPath, 'media');

  const webhookConfig = loadWebhookConfig(authDataPath);

  // Create media storage directory if it doesn't exist
  if (!fs.existsSync(mediaStoragePath)) {
    try {
      fs.mkdirSync(mediaStoragePath, { recursive: true });
      logger.info(`Created media storage directory: ${mediaStoragePath}`);
    } catch (error) {
      logger.error(`Failed to create media storage directory: ${error}`);
    }
  }

  // remove Chrome lock file if it exists
  try {
    fs.rmSync(authDataPath + '/SingletonLock', { force: true });
  } catch {
    // Ignore if file doesn't exist
  }

  const npx_args = { headless: true };
  const docker_args = {
    headless: true,
    userDataDir: authDataPath,
    args: ['--no-sandbox', '--single-process', '--no-zygote'],
  };

  const authStrategy =
    config.authStrategy === 'local' && !config.dockerContainer
      ? new LocalAuth({
          dataPath: authDataPath,
        })
      : new NoAuth();

  const puppeteer = config.dockerContainer ? docker_args : npx_args;

  const client = new Client({
    puppeteer,
    authStrategy,
    restartOnAuthFail: true,
  });

  // Create WhatsApp service instance for media operations
  let whatsappService: WhatsAppService;

  // Generate QR code when needed
  let qrCodeServerStarted = false;

  client.on('qr', async (qr: string) => {
    qrcode.generate(qr, { small: true });

    const canvas = createCanvas(300, 300);
    const ctx = canvas.getContext('2d');
    await qrcodepng.toCanvas(canvas, qr);

    const buffer = canvas.toBuffer('image/png');
    const imagePath = path.join(__dirname, 'qrcode.png');
    fs.writeFileSync(imagePath, buffer);


    if (qrCodeServerStarted) return;

    const app = express();
    const PORT = 3005;

    app.get('/qrcode', (_req: Request, res: Response) => {
      if (fs.existsSync(imagePath)) {
                res.sendFile(path.resolve(imagePath));
            } else {
                res.status(404).send('QR code not found');
            }
      });

    app.listen(PORT, () => {
      console.log(`QR code server at http://localhost:${PORT}/qrcode`);
    });

    qrCodeServerStarted = true;
  });

  // Handle ready event
  client.on('ready', async () => {
    try {
      await fetch('http://host.docker.internal:8000/set-connected', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ connected: true }),
      });
      logger.info('Client is ready!');
      whatsappService = new WhatsAppService(client);
    } catch (error) {
      logger.error('Failed to notify connection to server:', error);
    }
  });

  // Handle authenticated event
  client.on('authenticated', () => {
    logger.info('Authentication successful!');
    // Initialize WhatsAppService on authentication if not already initialized
    if (!whatsappService) {
      whatsappService = new WhatsAppService(client);
      logger.info('WhatsAppService initialized on authentication');
    }
  });

  // Handle auth failure event
  client.on('auth_failure', (msg: string) => {
    logger.error('Authentication failed:', msg);
  });

  // Handle disconnected event
  client.on('disconnected', (reason: string) => {
    try {
    fetch('http://host.docker.internal:8000/set-connected', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ connected: false }),
    });
    logger.warn('Client was disconnected:', reason);
  } catch (error) {
    logger.error('Failed to disconnect:', error);
  }
  });

  // Handle messages sent by this client (outgoing messages)
  client.on('message_create', async (message: Message) => {
    const contact = await message.getContact();
    logger.debug(`Own message: ${contact.pushname} (${contact.number}): ${message.body}`);

    if (!message.id.fromMe) return;

    // Ignore Butler messages
    if (message.body.startsWith(QUERY_PREFIX)) {
      logger.debug(`Skipping: Ignoring Butler message with prefix '${QUERY_PREFIX}`);
      return;
    }

    if (webhookConfig) {
      // Check filters
      const isGroup = message.to.includes('@g.us');
      const isSelfChat = !isGroup && message.to.split('@')[0] === client.info.wid.user;

      // Skip if filters don't match
      if (shouldSkipMessageByFilters(isGroup, isSelfChat, contact.number, webhookConfig.filters)) {
        return;
      }

      // Download media if present - always download all media types
      let mediaInfo = undefined;
      if (message.hasMedia && whatsappService) {
        try {
          logger.info(`Downloading media from message ${message.id._serialized}`);
          const mediaResponse = await whatsappService.downloadMediaFromMessage(
            message.id._serialized,
            mediaStoragePath
          );
          mediaInfo = {
            filePath: mediaResponse.filePath,
            mimetype: mediaResponse.mimetype,
            filename: mediaResponse.filename,
            filesize: mediaResponse.filesize,
          };
          logger.info(`Media downloaded successfully: ${mediaResponse.filename}`);
        } catch (error) {
          logger.error(`Failed to download media: ${error}`);
        }
      }

      // Send to webhook
      try {
        const response = await axios.post(
          webhookConfig.url,
          {
            from: contact.number,
            name: contact.pushname,
            message: message.body,
            isGroup: isGroup,
            timestamp: message.timestamp,
            messageId: message.id._serialized,
            hasMedia: message.hasMedia,
            mediaType: message.hasMedia ? message.type : undefined,
            mediaInfo: mediaInfo,
          },
          {
            headers: {
              'Content-Type': 'application/json',
              ...(webhookConfig.authToken
                ? { Authorization: `Bearer ${webhookConfig.authToken}` }
                : {}),
            },
          },
        );

        if (response.status < 200 || response.status >= 300) {
          logger.warn(`Webhook request failed with status ${response.status}`);
        }
      } catch (error) {
        logger.error('Error sending webhook:', error);
      }
    }
  });

  // Handle messages received from other users (incoming messages)
  client.on('message', async (message: Message) => {
    const contact = await message.getContact();
    logger.debug(`${contact.pushname} (${contact.number}): ${message.body}`);
  })

  return client;
}
