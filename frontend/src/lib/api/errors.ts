// Error codes are defined in the API contract (RFC 9457 Problem)

/**
 * User-facing messages per Problem `code` (RFC 9457). Branch on `code`
 * only; never show the server's `title`/`detail` verbatim.
 */
const MESSAGES: Record<string, string> = {
  bad_request: "The request could not be read. Please try again.",
  validation_error: "Some of the options are not valid. Please check them and try again.",
  file_too_large: "A file is larger than allowed.",
  too_many_files: "Too many files for this tool.",
  unsupported_type: "This file type is not supported by this tool.",
  type_mismatch: "These files cannot be processed together.",
  too_many_pages: "The document has more pages than allowed.",
  invalid_file: "The file appears to be damaged or is not a valid document.",
  file_encrypted: "The file is password protected. Please remove the password and try again.",
  url_blocked: "That address cannot be fetched.",
  rate_limited: "Too many requests. Please wait a moment and try again.",
  upstream_fetch_failed: "One of the pages could not be fetched.",
  processing_failed: "We could not process this file.",
  processing_timeout: "Processing took too long. Try a smaller file or fewer pages.",
  internal_error: "Something went wrong on our side.",
  not_found: "Not found.",
};

const GENERIC = "Something went wrong. Please try again.";

export function errorMessage(code: string | null | undefined): string {
  if (!code) return GENERIC;
  return (MESSAGES as Record<string, string>)[code] ?? GENERIC;
}
