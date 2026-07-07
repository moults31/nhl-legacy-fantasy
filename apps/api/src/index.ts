import Fastify from "fastify";
import cors from "@fastify/cors";
import { config } from "./config.js";
import { initDb } from "./db.js";
import { registerRoutes } from "./routes.js";

async function main() {
  initDb();

  const app = Fastify({ logger: true });
  await app.register(cors, { origin: config.corsOrigin });
  await registerRoutes(app);

  try {
    await app.listen({ port: config.port, host: "0.0.0.0" });
  } catch (err) {
    app.log.error(err);
    process.exit(1);
  }
}

main();
