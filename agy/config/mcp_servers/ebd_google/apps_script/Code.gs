/**
 * Google Apps Script Web App handler for the `ebd-google` MCP server.
 *
 * Single responsibility: duplicate a Teleprompter template document inside the
 * destination folder in personal My Drive (working around the Service Account
 * storageQuota=0 limitation) and return the new Google Doc's ID, name, and URL.
 *
 * IMPORTANT: Store the shared secret in Script Properties
 * (Project Settings -> Script Properties -> key: EBD_COPY_SECRET).
 * Never hardcode secrets in the repository.
 */

function doPost(e) {
  console.log("POST execution started. Checking authorization...");

  try {
    const payload = JSON.parse((e && e.postData && e.postData.contents) || "{}");
    const expectedSecret = PropertiesService.getScriptProperties().getProperty("EBD_COPY_SECRET");

    if (!expectedSecret || payload.secret !== expectedSecret) {
      console.warn("Authorization failed: Missing or invalid EBD_COPY_SECRET.");
      return jsonResponse({ ok: false, error: "Unauthorized: invalid or missing secret." });
    }

    if (payload.action !== "copy_file") {
      console.warn("Unsupported action received: " + payload.action);
      return jsonResponse({ ok: false, error: "Unsupported action: " + payload.action });
    }

    const templateFileId = payload.templateFileId;
    const folderId = payload.folderId;
    const newName = payload.newName;

    if (!templateFileId || !folderId || !newName) {
      console.error("Execution aborted: Missing templateFileId, folderId, or newName.");
      return jsonResponse({ ok: false, error: "Missing templateFileId, folderId, or newName." });
    }

    console.log('Copying template "' + templateFileId + '" into folder "' + folderId + '" as "' + newName + '"...');
    const templateFile = DriveApp.getFileById(templateFileId);
    const destFolder = DriveApp.getFolderById(folderId);
    const copy = templateFile.makeCopy(newName, destFolder);

    console.log('File copied successfully. New ID: "' + copy.getId() + '"');
    return jsonResponse({
      ok: true,
      id: copy.getId(),
      name: copy.getName(),
      url: copy.getUrl()
    });
  } catch (error) {
    console.error("An error occurred during POST execution: " + error.message);
    return jsonResponse({ ok: false, error: String(error) });
  }
}

/**
 * Helper function to return a JSON HTTP response
 */
function jsonResponse(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
