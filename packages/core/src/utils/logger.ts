// ============================================================
// Structured Logger
// ============================================================

import pino from 'pino';
import { TestingMetadata } from '../types';

const isDev = process.env.NODE_ENV !== 'production';

export function createLogger(name: string, metadata?: TestingMetadata) {
  const base = metadata
    ? {
        test_run_id: metadata.test_run_id,
        scenario: metadata.scenario_name,
        worker: metadata.worker_id,
        traffic_type: metadata.traffic_type,
      }
    : {};

  return pino({
    name,
    level: process.env.LOG_LEVEL || (isDev ? 'debug' : 'info'),
    transport: isDev
      ? {
          target: 'pino-pretty',
          options: {
            colorize: true,
            translateTime: 'SYS:standard',
            ignore: 'pid,hostname',
          },
        }
      : undefined,
    base,
    redact: {
      paths: ['password', 'token', 'secret', 'authorization', 'cookie'],
      censor: '***',
    },
  });
}

/** Pre-configured root logger */
export const logger = createLogger('videoqa');
