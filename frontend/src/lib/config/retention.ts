/**
 * DISPLAY-ONLY copy of the file retention schedule (docs/architecture.md §1,
 * docs/privacy.md). The server settings are the source of truth; keep these
 * numbers in sync with them. Never shorten them here to make copy sound better.
 */
export const retention = {
  /** Output is deleted this many minutes after the first completed download. */
  afterDownloadMinutes: 2,
  /** Output is deleted this many minutes after creation if never downloaded. */
  undownloadedMinutes: 60,
  /** Scheduled cleanup interval. */
  sweepEveryMinutes: 5,
  /** Hard cap: anything older is removed unconditionally ([N] in privacy.md). */
  hardCapHours: 2,
} as const;

/** The one approved retention statement (docs/privacy.md §1). Use it wherever retention is stated. */
export const retentionSentence =
  "Files are deleted automatically, usually within minutes of your download and no later than about 2 hours after processing.";
