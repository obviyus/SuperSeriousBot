import type { AppDependencies } from "./dependencies.ts";

export function isAdmin(dependencies: AppDependencies, userId: number | string): boolean {
  return dependencies.config.admins.has(String(userId));
}
