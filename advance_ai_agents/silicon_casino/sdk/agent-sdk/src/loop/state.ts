export type TurnState = {
  turn_id?: string;
  my_seat?: number;
  current_actor_seat?: number;
};

export class TurnTracker {
  private readonly seenTurns = new Set<string>();

  shouldRequestDecision(state: TurnState): boolean {
    const turnID = typeof state.turn_id === "string" ? state.turn_id : "";
    const mySeat = Number(state.my_seat ?? -1);
    const actorSeat = Number(state.current_actor_seat ?? -2);
    if (!turnID || mySeat !== actorSeat) {
      return false;
    }
    if (this.seenTurns.has(turnID)) {
      return false;
    }
    this.seenTurns.add(turnID);
    return true;
  }
}
