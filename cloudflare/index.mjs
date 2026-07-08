// Worker entry for Cloudflare Containers: routes every request to a single
// container instance running the FastAPI app (max_instances: 1 keeps SQLite
// single-writer). Set the JWT secret once with:
//   npx wrangler secret put ARDHI_JWT_SECRET

import { Container, getContainer } from "@cloudflare/containers";

export class ArdhiContainer extends Container {
  defaultPort = 8000;
  sleepAfter = "15m";

  constructor(ctx, env) {
    super(ctx, env);
    this.envVars = {
      ARDHI_JWT_SECRET: env.ARDHI_JWT_SECRET ?? "",
      ARDHI_DATA_DIR: "/data",
      // Set via `wrangler secret put DATABASE_URL` (Supabase) to make data
      // durable — otherwise SQLite on the ephemeral container disk is used.
      DATABASE_URL: env.DATABASE_URL ?? "",
    };
  }
}

export default {
  async fetch(request, env) {
    return getContainer(env.ARDHI).fetch(request);
  },
};
