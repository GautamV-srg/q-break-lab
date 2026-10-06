// The message and keys the mock fixtures were recorded with. Kept apart from the fixtures
// themselves so pages can read them without loading the (large, lazy) mock engine.

export const MOCK_MESSAGE = "Hi judges!";

/** Organization key per key size in the recorded runs. Using it in mock mode replays a real run exactly. */
export const MOCK_KEYS: Record<number, string> = { 4: "1001", 6: "100110", 8: "10011001" };
