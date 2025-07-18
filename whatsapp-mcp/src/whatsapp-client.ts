import { Client, LocalAuth, Message, NoAuth } from 'whatsapp-web.js';
import qrcode from 'qrcode-terminal';
import logger from './logger';
import fs from 'fs';
import path from 'path';
import axios from 'axios';
import qrcodepng from 'qrcode';
import { createCanvas } from 'canvas';
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
  const environment = process.env.ENVIRONMENT || 'local';
  const webhookConfigPath = path.join(dataPath, `webhook.${environment}.json`);

  // Check if file exists first
  if (fs.existsSync(webhookConfigPath)) {
    try {
      return JSON.parse(fs.readFileSync(webhookConfigPath, 'utf8'));
    } catch (error) {
      console.error(`Error reading webhook config file: ${error}`);
    }
  }
  if (environment === 'local' || environment === 'development') {
    return {
      "url": "http://webhook:8080/webhook",
      "filters": {
        "allowPrivate": false,
        "allowGroups": false,
        "allowSelfChat": true
      }
    };
  } else {
    return {
      "url": "http://localhost:8080/webhook",
      "filters": {
        "allowPrivate": false,
        "allowGroups": false,
        "allowSelfChat": true
      }
    };
  }
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


  const commonArgs = [
    "--disable-accelerated-2d-canvas",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-breakpad",
    "--disable-cache",
    "--disable-component-extensions-with-background-pages",
    "--disable-crash-reporter",
    "--disable-dev-shm-usage",
    "--disable-extensions",
    "--disable-gpu",
    "--disable-hang-monitor",
    "--disable-ipc-flooding-protection",
    "--disable-mojo-local-storage",
    "--disable-notifications",
    "--disable-popup-blocking",
    "--disable-print-preview",
    "--disable-prompt-on-repost",
    "--disable-renderer-backgrounding",
    "--disable-software-rasterizer",
    "--ignore-certificate-errors",
    "--log-level=3",
    "--no-default-browser-check",
    "--no-first-run",
    "--no-sandbox",
    "--no-zygote",
    "'--enable-logging",
    "--renderer-process-limit=100",
    "--enable-gpu-rasterization",
    "--enable-zero-copy",
    "--unlimited-storage",
    "--disable-storage-reset",
    "--allow-file-access",
    "--user-data-dir=/tmp/chrome-profile",
    "--disable-web-security",
    "--disable-features=IsolateOrigins,site-per-process"
  ];

  let puppeteer: any;

  const environment = process.env.ENVIRONMENT || 'development';

  let authStrategy: any;
  if (environment === 'production') {
    authStrategy = new LocalAuth({ dataPath: authDataPath });

    puppeteer = {
      headless: true,
      executablePath: '/usr/bin/chromium',
      args: commonArgs,
    };
  } else if (config.authStrategy === 'local' && !config.dockerContainer) {
    authStrategy = new LocalAuth({ dataPath: authDataPath });

    puppeteer = {
      headless: true,
      userDataDir: authDataPath,
      args: commonArgs,
    };
  } else {
    authStrategy = new NoAuth();

    puppeteer = {
      headless: true,
      args: commonArgs,
    };
  }

  const client = new Client({
    puppeteer,
    authStrategy,
    restartOnAuthFail: true,
  });
  // Create WhatsApp service instance for media operations
  let whatsappService: WhatsAppService;

  client.on('qr', async (qr: string) => {
    qrcode.generate(qr, { small: true });

    const canvas = createCanvas(300, 300);
    const ctx = canvas.getContext('2d');
    await qrcodepng.toCanvas(canvas, qr);

    const buffer = canvas.toBuffer('image/png');
    const imagePath = path.join(__dirname, 'qrcode.png');
    fs.writeFileSync(imagePath, buffer);

  });

  // Handle ready event
  client.on('ready', async () => {
    const maxRetries = 10;
  for (let i = 0; i < maxRetries; i++) {
    try {
      const res = await fetch('http://localhost:8080/set-connected', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ connected: true }),
      });
      if (res.ok) {
        console.log('Webhook notified successfully');
        return;
      }
    } catch (err) {
      console.log(`Webhook not ready yet (attempt ${i + 1})...`);
    }
    await new Promise((r) => setTimeout(r, 3000));
  }
  console.error('Failed to notify webhook after retries');
  });
  client.on('error', (error) => {
    console.error('Error occurred:', error);
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
    fetch('http://localhost:8080/set-connected', {
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
