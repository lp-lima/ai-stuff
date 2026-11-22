/**
 * Google Apps Script Web App auxiliar do MCP `ebd-google`.
 *
 * Função única: duplicar um arquivo modelo de Teleprompter dentro da pasta
 * destino no seu My Drive pessoal (contornando o limite storageQuota=0 da
 * Service Account) e retornar o ID/URL do novo Google Doc.
 *
 * IMPORTANTE: Guarde o token secreto nas Propriedades do Script
 * (Configurações do Projeto -> Propriedades do script -> chave: EBD_COPY_SECRET),
 * nunca hardcoded no repositório.
 */

function doPost(e) {
  try {
    var payload = JSON.parse(e.postData.contents || "{}");
    var expectedSecret = PropertiesService.getScriptProperties().getProperty("EBD_COPY_SECRET");

    if (!expectedSecret || payload.secret !== expectedSecret) {
      return jsonResponse({ ok: false, error: "Unauthorized: invalid or missing secret." });
    }

    if (payload.action !== "copy_file") {
      return jsonResponse({ ok: false, error: "Unsupported action: " + payload.action });
    }

    var templateFileId = payload.templateFileId;
    var folderId = payload.folderId;
    var newName = payload.newName;

    if (!templateFileId || !folderId || !newName) {
      return jsonResponse({ ok: false, error: "Missing templateFileId, folderId, or newName." });
    }

    var templateFile = DriveApp.getFileById(templateFileId);
    var destFolder = DriveApp.getFolderById(folderId);
    var copy = templateFile.makeCopy(newName, destFolder);

    return jsonResponse({
      ok: true,
      id: copy.getId(),
      name: copy.getName(),
      url: copy.getUrl()
    });
  } catch (err) {
    return jsonResponse({ ok: false, error: String(err) });
  }
}

function jsonResponse(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
