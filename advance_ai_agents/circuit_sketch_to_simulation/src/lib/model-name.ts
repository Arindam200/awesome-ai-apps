// Display name for the configured model. Pure, so client components can use it too.
export function modelName(model: string | undefined) {
  if (!model || /inkling-2-small/i.test(model)) return "Inkling 2 Small";
  return model.split("/").pop() ?? model;
}
