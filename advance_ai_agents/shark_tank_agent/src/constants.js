export const starterPrompt =
  "I run a social media agency for local restaurants. We do content shoots, reels, ads, and influencer collabs. We made $18k revenue last month with 42% margin, have 11 recurring clients, and want $150k to hire editors and build an AI reporting dashboard.";

export const stages = [
  { key: "idea", label: "Idea", hint: "Pre-revenue validation questions" },
  { key: "early", label: "Early", hint: "First customers, revenue, retention, repeatability" },
  { key: "scaling", label: "Scaling", hint: "Hiring, systems, unit economics, expansion" },
  { key: "fundraising", label: "Raise", hint: "Ask, valuation, risk, and terms" },
];

export const objectives = [
  { key: "clarity", label: "Clarity", hint: "Sharper narrative and customer pain" },
  { key: "growth", label: "Growth", hint: "Channels, scaling loops, partnerships" },
  { key: "economics", label: "Economics", hint: "Pricing, margin, payback, retention" },
  { key: "deal", label: "Deal", hint: "Funding ask, valuation, and conditions" },
];

export const lengths = [
  { key: "quick", label: "Quick 3", hint: "One question from each shark" },
  { key: "full", label: "Full 6", hint: "Two questions from each shark" },
];

export const stageColors = {
  left: 0x7eb6ff,
  right: 0xffffff,
  judge: 0xf2e6c9,
  room: 0x06080d,
};

export const seatLayout = {
  nemotron: { position: [-1.92, 0.18, -3.08], rotation: 0.1, scale: 1.16, seated: true },
  judge: { position: [0, 0.18, -3.08], rotation: 0, scale: 1.2, seated: true },
  deepseek: { position: [1.92, 0.18, -3.08], rotation: -0.1, scale: 1.16, seated: true },
};

export const podiumLayout = {
  nemotron: [-1.92, 0.06, -3.08],
  judge: [0, 0.06, -3.08],
  deepseek: [1.92, 0.06, -3.08],
};

export const deskLayout = {
  position: [0, 0.1, -2.58],
};

export const cameraShots = {
  wide: { x: 0, y: 1.1, z: 5.35, lookX: 0, lookY: 1.82, lookZ: -3.08 },
  judge: { x: 0, y: 1.08, z: 5.0, lookX: 0, lookY: 1.86, lookZ: -3.12 },
  nemotron: { x: -0.62, y: 1.08, z: 5.12, lookX: -1.42, lookY: 1.84, lookZ: -3.12 },
  deepseek: { x: 0.62, y: 1.08, z: 5.12, lookX: 1.42, lookY: 1.84, lookZ: -3.12 },
  tie: { x: 0, y: 1.1, z: 5.22, lookX: 0, lookY: 1.82, lookZ: -3.08 },
  push: { x: 0, y: 1.06, z: 4.78, lookX: 0, lookY: 1.84, lookZ: -3.1 },
};
