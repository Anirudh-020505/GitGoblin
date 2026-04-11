// api/index.ts
// This is the Vercel serverless entry point for GitGoblin.
// Vercel will call this function for every incoming request.

import express, { Request, Response, NextFunction } from 'express';
import dotenv from 'dotenv';
import crypto from 'crypto';
import { handleGithubWebhook } from '../src/controllers/webhook.controller';

dotenv.config();

const app = express();

// Raw body parsing for webhook signature verification
app.use(express.json({
  verify: (req: any, res: Response, buf: Buffer) => {
    req.rawBody = buf;
  }
}));

// GitHub Webhook Signature Verification Middleware
const verifyGithubSignature = (req: Request, res: Response, next: NextFunction): void => {
  const signature = req.headers['x-hub-signature-256'] as string;

  if (!signature) {
    res.status(401).send('Unauthorized: No signature found');
    return;
  }

  const WEBHOOK_SECRET = process.env.GITHUB_WEBHOOK_SECRET;
  if (!WEBHOOK_SECRET) {
    res.status(500).send('Server misconfiguration: missing webhook secret');
    return;
  }

  const hmac = crypto.createHmac('sha256', WEBHOOK_SECRET);
  const rawBody = (req as any).rawBody;
  const expectedDigest = 'sha256=' + hmac.update(rawBody).digest('hex');

  try {
    const isValid = crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expectedDigest));
    if (!isValid) {
      res.status(401).send('Unauthorized: Signature mismatch');
      return;
    }
  } catch {
    res.status(401).send('Unauthorized: Signature mismatch');
    return;
  }

  next();
};

// Health check
app.get('/health', (req, res) => {
  res.status(200).send('GitGoblin is healthy and watching 😈');
});

// Webhook handler
app.post('/webhook', verifyGithubSignature, handleGithubWebhook);

// Export for Vercel
export default app;
