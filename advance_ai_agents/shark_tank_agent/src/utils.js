export function founderName(key) {
  if (key === "nemotron") return "MiniMax";
  if (key === "deepseek") return "DeepSeek";
  if (key === "judge") return "Nemotron";
  if (key === "deal") return "Deal";
  if (key === "conditional_deal") return "Conditional deal";
  if (key === "no_deal") return "No deal";
  return "Panel";
}

export function winnerText(winner) {
  if (winner === "deal" || winner === "conditional_deal" || winner === "no_deal") {
    return founderName(winner);
  }
  if (winner === "tie") return "Tie round";
  return `${founderName(winner)} leads`;
}

export function seatLabel(seat) {
  if (seat === "nemotron") return "MiniMax";
  if (seat === "deepseek") return "DeepSeek";
  if (seat === "judge") return "Nemotron";
  return "Shark";
}
