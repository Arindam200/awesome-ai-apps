import {
  createHotkeyRecorderState,
  orderHotkeyCodes,
  updateHotkeyRecorderState,
} from './hotkeyRecorder';

function assertEqual<T>(actual: T, expected: T, name: string) {
  if (actual !== expected) {
    throw new Error(`${name}: expected ${expected}, got ${actual}`);
  }
}

function assertDeepEqual(actual: unknown, expected: unknown, name: string) {
  const actualJson = JSON.stringify(actual);
  const expectedJson = JSON.stringify(expected);
  if (actualJson !== expectedJson) {
    throw new Error(`${name}: expected ${expectedJson}, got ${actualJson}`);
  }
}

function apply(
  state = createHotkeyRecorderState(),
  code: string,
  pressed: boolean,
) {
  const next = updateHotkeyRecorderState(state, code, pressed);
  return next;
}

{
  let result = apply(undefined, 'ControlLeft', true);
  assertDeepEqual(result.state.draftCodes, ['ControlLeft'], 'tracks first pressed key');
  assertEqual(result.commitCodes, null, 'does not commit until release');

  result = apply(result.state, 'ControlLeft', false);
  assertDeepEqual(result.commitCodes, ['ControlLeft'], 'commits single key on release');

  result = apply(createHotkeyRecorderState(), 'KeyK', true);
  assertDeepEqual(result.state.draftCodes, ['KeyK'], 'starts a new recording state cleanly');
  assertEqual(result.commitCodes, null, 'new keydown does not include old released keys');
}

{
  let result = apply(undefined, 'ControlLeft', true);
  result = apply(result.state, 'KeyK', true);
  assertDeepEqual(result.state.draftCodes, ['ControlLeft', 'KeyK'], 'records keyboard combo draft');

  result = apply(result.state, 'ControlLeft', false);
  assertEqual(result.commitCodes, null, 'keyboard combo waits for final release');
  assertDeepEqual(result.state.draftCodes, ['ControlLeft', 'KeyK'], 'released combo member stays in draft only');

  result = apply(result.state, 'KeyK', false);
  assertDeepEqual(result.commitCodes, ['ControlLeft', 'KeyK'], 'keyboard combo commits after all keys release');
  assertDeepEqual(result.state, createHotkeyRecorderState(), 'state resets after commit');
}

{
  let result = apply(undefined, 'Mouse4', true);
  assertDeepEqual(result.state.draftCodes, ['Mouse4'], 'tracks mouse button as draft');
  assertEqual(result.commitCodes, null, 'mouse button does not commit on mousedown');

  result = apply(result.state, 'ControlLeft', true);
  assertDeepEqual(result.state.draftCodes, ['ControlLeft', 'Mouse4'], 'records keyboard plus mouse combo');
  assertEqual(result.commitCodes, null, 'combo does not commit while inputs remain pressed');

  result = apply(result.state, 'Mouse4', false);
  assertEqual(result.commitCodes, null, 'releasing one combo member does not commit early');

  result = apply(result.state, 'ControlLeft', false);
  assertDeepEqual(result.commitCodes, ['ControlLeft', 'Mouse4'], 'commits combo after final release');
}

{
  let result = apply(undefined, 'ControlLeft', true);
  result = apply(result.state, 'Mouse5', true);
  assertDeepEqual(result.state.draftCodes, ['ControlLeft', 'Mouse5'], 'records mouse button pressed after keyboard');

  result = apply(result.state, 'ControlLeft', false);
  assertEqual(result.commitCodes, null, 'mouse combo keeps waiting while mouse remains pressed');

  result = apply(result.state, 'Mouse5', false);
  assertDeepEqual(result.commitCodes, ['ControlLeft', 'Mouse5'], 'commits mouse-last combo after mouse release');
}

assertDeepEqual(orderHotkeyCodes(['Mouse4', 'ControlLeft']), ['ControlLeft', 'Mouse4'], 'orders mouse after modifiers');
