import { z } from "zod";

export const requirementsComplianceToolConfig = z.object({
  name: z.literal("requirementsCompliance"),
  label: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
  enabled: z.boolean().nullable().optional(),
  config: z.object({}).nullable().optional(),
});
export type requirementsComplianceToolConfigType = z.infer<typeof requirementsComplianceToolConfig>;
export const DEFAULT_REQUIREMENTS_COMPLIANCE_TOOL_CONFIG = {
  label: "requirementsCompliance",
  description: "",
  config: {},
  enabled: false,
};
