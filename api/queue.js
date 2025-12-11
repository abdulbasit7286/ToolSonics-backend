import { Queue } from "bullmq";
import IORedis from "ioredis";

// 👇 Yahan apna pure Upstash Redis URL paste karo (TCP URL)
const REDIS_URL = "rediss://default:ASZoAAImcDEwOGUzMDQ1NzM1ODQ0ZGVhYWFmYWIzNWE1Mjg2NGZjOHAxOTgzMg@big-garfish-9832.upstash.io:6379";

const connection = new IORedis(REDIS_URL, {
  tls: {}   // ⚠️ Upstash ALWAYS needs TLS
});

export const pdfQueue = new Queue("pdfJobs", { connection });
