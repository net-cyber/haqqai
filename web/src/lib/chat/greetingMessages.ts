export const GREETING_MESSAGES = [
  "What should we scout, draft, or report on today?",
  "Let's get started.",
];

export function getRandomGreeting(): string {
  return GREETING_MESSAGES[
    Math.floor(Math.random() * GREETING_MESSAGES.length)
  ] as string;
}
