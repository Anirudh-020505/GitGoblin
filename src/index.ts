// src/index.ts

import express, { Request, Response, NextFunction } from 'express';
import dotenv from 'dotenv';
import crypto from 'crypto';
import { handleGithubWebhook } from './controllers/webhook.controller';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

/**
 * PRODUCTION SECURITY: Raw Body Parsing
 * To verify a GitHub webhook signature, we need the EXACT raw bytes of the request body.
 * If Express parses it into JSON first, the spaces/formatting change, and the signature will fail.
 */
app.use(express.json({
  verify: (req: any, res: Response, buf: Buffer) => {
    req.rawBody = buf; // Save the raw buffer for the crypto check
  }
}));

/**
 * PRODUCTION SECURITY: Webhook Signature Verification Middleware
 * This ensures the request actually came from GitHub and not a malicious bot.
 */
const verifyGithubSignature = (req: Request, res: Response, next: NextFunction): void => {
  const signature = req.headers['x-hub-signature-256'] as string;
  
  if (!signature) {
    console.warn('[Security] Missing webhook signature.');
    res.status(401).send('Unauthorized: No signature found');
    return;
  }

  // We use the Webhook Secret you define in your GitHub App settings
  const WEBHOOK_SECRET = process.env.GITHUB_WEBHOOK_SECRET;
  if (!WEBHOOK_SECRET) {
    throw new Error('CRITICAL: GITHUB_WEBHOOK_SECRET is missing.');
  }

  // Create an HMAC hash using SHA-256 and your secret, matching GitHub's algorithm
  const hmac = crypto.createHmac('sha256', WEBHOOK_SECRET);
  const rawBody = (req as any).rawBody; 
  const expectedDigest = 'sha256=' + hmac.update(rawBody).digest('hex');

  // Use crypto.timingSafeEqual to prevent timing attacks
  const isValid = crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expectedDigest));

  if (!isValid) {
    console.error('[Security] Webhook signature mismatch! Rejecting payload.');
    res.status(401).send('Unauthorized: Signature mismatch');
    return;
  }

  // If the signature matches, pass the request to your controller
  next();
};

// --- ROUTES ---

// Health check route (Good for deployment platforms like Render or Railway)
app.get('/health', (req, res) => {
  res.status(200).send('GitGoblin is healthy and watching 😈');
});

// The main Webhook listener
app.post('/api/webhook', verifyGithubSignature, handleGithubWebhook);

// --- START SERVER ---

app.listen(PORT, () => {
  console.log(`🚀 GitGoblin Server is running on port ${PORT}`);
  console.log(`🔒 Secure Signature Verification is ACTIVE.`);
});