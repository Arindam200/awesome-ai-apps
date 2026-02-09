import test from "node:test";
import assert from "node:assert/strict";

import { TurnTracker } from "./state.js";

test("TurnTracker requests exactly once for my new turn", () => {
  const tracker = new TurnTracker();
  const state = { turn_id: "turn_1", my_seat: 0, current_actor_seat: 0 };
  assert.equal(tracker.shouldRequestDecision(state), true);
  assert.equal(tracker.shouldRequestDecision(state), false);
});

test("TurnTracker ignores opponent turn", () => {
  const tracker = new TurnTracker();
  const state = { turn_id: "turn_2", my_seat: 0, current_actor_seat: 1 };
  assert.equal(tracker.shouldRequestDecision(state), false);
});

