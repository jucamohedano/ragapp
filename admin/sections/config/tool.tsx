import {
  DEFAULT_TOOL_CONFIG,
  ToolConfigSchema,
  ToolConfigType,
  getToolsConfig,
  updateToolConfig,
} from "@/client/tool";
import { Checkbox } from "@/components/ui/checkbox";
import { ExpandableSection } from "@/components/ui/custom/expandableSection";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { toast } from "@/components/ui/use-toast";
import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm, useWatch } from "react-hook-form";
import { ImageGeneratorConfig } from "./tools/image_generator";
import { E2BInterpreterConfig } from "./tools/interpreter";
import { OpenAPIConfig } from "./tools/openapi";
import { QdrantClient } from "@qdrant/js-client-rest";

const checkCollectionExists = async (collectionName: string) => {
  const client = new QdrantClient({ host: "localhost", port: 6333 });

  try {
    const collectionsResponse = await client.getCollections();
    return collectionsResponse.collections.some(
      (collection) => collection.name === collectionName
    );
  } catch (error) {
    console.error(`Error checking collection '${collectionName}':`, error);
    throw error;
  }
};

const checkRequirementsComplianceAndCollections = async () => {
  try {
    const collectionsExist = await Promise.all([
      checkCollectionExists("requirement"),
      checkCollectionExists("description"),
    ]);
    return {
      requirementCollectionExists: collectionsExist[0],
      descriptionCollectionExists: collectionsExist[1],
    };
  } catch (error) {
    console.error(
      "Error checking Requirements Compliance tool and collections:",
      error
    );
    throw error;
  }
};

export const ToolConfig = () => {
  const form = useForm<ToolConfigType>({
    resolver: zodResolver(ToolConfigSchema),
    defaultValues: DEFAULT_TOOL_CONFIG,
  });

  const onSubmit = async (tool_name: string, data: any) => {
    if (tool_name === "requirementsCompliance" && data.enabled) {
      try {
        const complianceResults = await checkRequirementsComplianceAndCollections();

        if (
          complianceResults &&
          (!complianceResults.requirementCollectionExists ||
            !complianceResults.descriptionCollectionExists)
        ) {
          data.enabled = false;
          form.reset(data)
          toast({
            title: "Compliance Error",
            description:
              "The requirement and description collections must exist and be populated before using the Requirement Compliance agent.",
            className: "text-red-500",
          });
        }
      } catch (error) {
        data.enabled = false;
        form.reset(data)
        console.error("Compliance check failed:", error);
        toast({
          title: "Error",
          description:
            "An error occurred while performing the compliance check.",
          className: "text-red-500",
        });
      }
    }

    await updateToolConfig(tool_name, data).catch((error) => {
      toast({
        title: `Could not update ${tool_name} config`,
        variant: "destructive",
      });
    });
  };

  useEffect(() => {
    getToolsConfig().then((data) => {
      form.reset(data);
    });
  }, [form]);

  return (
    <ExpandableSection
      name="agent-config"
      title={"Agent Config"}
      description="Config tools and agent"
    >
      <Form {...form}>
        <form className="space-y-4 mb-4">
          <div className="flex flex-col space-y-4">
            <FormField
              control={form.control}
              name="requirementsCompliance"
              render={({ field }) => (
                <FormItem
                  key="requirementsCompliance"
                  className="flex flex-row items-center space-x-3 space-y-0"
                >
                  <FormControl>
                    <Checkbox
                      checked={field.value.enabled ?? false}
                      onCheckedChange={async (checked) => {
                        field.onChange({
                          ...field.value,
                          enabled: checked,
                        });
                        await onSubmit(
                          "requirementsCompliance",
                          form.getValues().requirementsCompliance
                        );
                      }}
                    />
                  </FormControl>
                  <div>
                    <FormLabel className="font-normal">
                      {field.value.label}
                    </FormLabel>
                    <FormMessage />
                    <FormDescription>
                      Use this agent after populating Requirements and
                      Description source to generate a compliance report
                    </FormDescription>
                  </div>
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="duckduckgo"
              render={({ field }) => (
                <FormItem
                  key="duckduckgo"
                  className="flex flex-row items-center space-x-3 space-y-0"
                >
                  <FormControl>
                    <Checkbox
                      checked={field.value.enabled ?? false}
                      onCheckedChange={async (checked) => {
                        field.onChange({
                          ...field.value,
                          enabled: checked,
                        });
                        await onSubmit(
                          "duckduckgo",
                          form.getValues().duckduckgo
                        );
                      }}
                    />
                  </FormControl>
                  <div>
                    <FormLabel className="font-normal">
                      {field.value.label}
                    </FormLabel>
                    <FormMessage />
                    <FormDescription>
                      {field.value.description}
                    </FormDescription>
                  </div>
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="wikipedia"
              render={({ field }) => (
                <FormItem
                  key="wikipedia"
                  className="flex flex-row items-center space-x-3 space-y-0"
                >
                  <FormControl>
                    <Checkbox
                      checked={field.value.enabled ?? false}
                      onCheckedChange={async (checked) => {
                        field.onChange({
                          ...field.value,
                          enabled: checked,
                        });
                        await onSubmit(
                          "wikipedia",
                          form.getValues().wikipedia
                        );
                      }}
                    />
                  </FormControl>
                  <div>
                    <FormLabel className="font-normal">
                      {field.value.label}
                    </FormLabel>
                    <FormMessage />
                    <FormDescription>
                      {field.value.description}
                    </FormDescription>
                  </div>
                </FormItem>
              )}
            />
            <OpenAPIConfig form={form} onSubmit={onSubmit} />
            <E2BInterpreterConfig form={form} onSubmit={onSubmit} />
            <ImageGeneratorConfig form={form} onSubmit={onSubmit} />
          </div>
        </form>
      </Form>
    </ExpandableSection>
  );
};
