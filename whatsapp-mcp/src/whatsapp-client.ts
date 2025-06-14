import { Client, LocalAuth, Message, NoAuth } from 'whatsapp-web.js';
import qrcode from 'qrcode-terminal';
import logger from './logger';
import fs from 'fs';
import path from 'path';
import axios from 'axios';
import qrcodepng from 'qrcode';
import { createCanvas } from 'canvas';
import express, { Request, Response } from 'express';
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
  };
}

function loadWebhookConfig(dataPath: string): WebhookConfig | undefined {
  const webhookConfigPath = path.join(dataPath, 'webhook.json');
  if (!fs.existsSync(webhookConfigPath)) {
    return undefined;
  }
  return JSON.parse(fs.readFileSync(webhookConfigPath, 'utf8'));
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
  } catch (error) {
    logger.error('Failed to notify connection to server:', error);
  }
  });

  // Handle authenticated event
  client.on('authenticated', () => {
    logger.info('Authentication successful!');
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

  client.on('message_create', async (message: Message) => {
    const contact = await message.getContact();
    if (message.id.fromMe) {
      logger.debug(`Own message: ${contact.pushname} (${contact.number}): ${message.body}`);
      client.emit('message', message);
    }
  });

  // Handle incoming messages
  client.on('message', async (message: Message) => {
    const contact = await message.getContact();
    logger.debug(`${contact.pushname} (${contact.number}): ${message.body}`);

    // Process webhook if configured and if the message is from the bot
    if (webhookConfig) {
      // Check filters
      const isGroup = message.from.includes('@g.us');

      // Skip if filters don't match
      if (
        (isGroup && webhookConfig.filters?.allowGroups === false) ||
        (!isGroup && webhookConfig.filters?.allowPrivate === false) ||
        (webhookConfig.filters?.allowedNumbers?.length &&
          !webhookConfig.filters.allowedNumbers.includes(contact.number))
      ) {
        return;
      }

      // Send to webhook
      try {
        const response = await axios.post(
          webhookConfig.url,
          {
            from: contact.number,
            name: contact.pushname,
            message: message.body,
            isGroup,
            timestamp: message.timestamp,
            messageId: message.id._serialized,
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

  return client;
}
