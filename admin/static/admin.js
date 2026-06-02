const state = {
  selectedPromptId: null,
  selectedDocument: null,
};

const promptList = document.getElementById('promptList');
const promptEditor = document.getElementById('promptEditor');
const promptPathBadge = document.getElementById('promptPathBadge');
const promptUpdated = document.getElementById('promptUpdated');
const promptStatus = document.getElementById('promptStatus');
const promptCount = document.getElementById('promptCount');

const documentList = document.getElementById('documentList');
const documentName = document.getElementById('documentName');
const documentEditor = document.getElementById('documentEditor');
const documentStatus = document.getElementById('documentStatus');
const docCount = document.getElementById('docCount');
const lastRefresh = document.getElementById('lastRefresh');

function setStatus(element, message, type = '') {
  element.textContent = message;
  element.className = `status-line ${type}`.trim();
}

function formatDate(value) {
  if (!value) {
    return 'Never';
  }
  return new Date(value).toLocaleString();
}

async function apiFetch(url, options) {
  const response = await fetch(url, options);
  if (response.status === 401) {
    window.location.href = '/admin/login';
    throw new Error('Unauthorized');
  }
  return response;
}

function renderPromptList(items) {
  promptCount.textContent = String(items.length);
  promptList.innerHTML = '';
  for (const item of items) {
    const row = document.createElement('div');
    row.className = `list-item ${state.selectedPromptId === item.id ? 'active' : ''}`.trim();
    row.innerHTML = `<strong>${item.name}</strong><small>${item.path}</small><small>Updated ${formatDate(item.updated_at)}</small>`;
    row.addEventListener('click', () => loadPrompt(item.id));
    promptList.appendChild(row);
  }
}

function renderDocumentList(items) {
  docCount.textContent = String(items.length);
  documentList.innerHTML = '';
  for (const item of items) {
    const row = document.createElement('div');
    row.className = `list-item ${state.selectedDocument === item.name ? 'active' : ''}`.trim();
    const badgeClass = item.status === 'stale' ? 'badge stale' : 'badge';
    row.innerHTML = `<strong>${item.name}</strong><small>${item.size} bytes</small><small>Updated ${formatDate(item.updated_at)}</small><div class="${badgeClass}">${item.status}</div>`;
    row.addEventListener('click', () => loadDocument(item.name));
    documentList.appendChild(row);
  }
}

async function loadPrompts() {
  const response = await apiFetch('/admin/api/prompts');
  const data = await response.json();
  renderPromptList(data.items || []);
  if (!state.selectedPromptId && data.items && data.items.length > 0) {
    await loadPrompt(data.items[0].id);
  }
}

async function loadPrompt(id) {
  state.selectedPromptId = id;
  const response = await apiFetch(`/admin/api/prompts/${encodeURIComponent(id).replace(/%2F/g, '/')}`);
  const data = await response.json();
  promptPathBadge.textContent = data.path;
  promptUpdated.textContent = `Last updated ${formatDate(data.updated_at)}`;
  promptEditor.value = data.content;
  setStatus(promptStatus, '');
  await loadPrompts();
}

async function savePrompt() {
  if (!state.selectedPromptId) {
    setStatus(promptStatus, 'Select a prompt first.', 'error');
    return;
  }
  const response = await apiFetch(`/admin/api/prompts/${encodeURIComponent(state.selectedPromptId).replace(/%2F/g, '/')}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: promptEditor.value }),
  });
  const data = await response.json();
  if (!response.ok) {
    setStatus(promptStatus, data.detail || 'Unable to save prompt.', 'error');
    return;
  }
  promptUpdated.textContent = `Last updated ${formatDate(data.updated_at)}`;
  setStatus(promptStatus, data.message, 'success');
  await loadPrompts();
}

async function loadKnowledgeBase() {
  const response = await apiFetch('/admin/api/knowledge-base/documents');
  const data = await response.json();
  renderDocumentList(data.items || []);
  docCount.textContent = String(data.status?.document_count || 0);
  lastRefresh.textContent = formatDate(data.status?.last_refreshed_at);
  if (!state.selectedDocument && data.items && data.items.length > 0) {
    await loadDocument(data.items[0].name);
  }
}

async function loadDocument(name) {
  state.selectedDocument = name;
  const response = await apiFetch(`/admin/api/knowledge-base/documents/${encodeURIComponent(name)}`);
  const data = await response.json();
  if (!response.ok) {
    setStatus(documentStatus, data.detail || 'Unable to load document.', 'error');
    return;
  }
  documentName.value = data.name;
  documentEditor.value = data.content;
  setStatus(documentStatus, '');
  await loadKnowledgeBase();
}

async function saveDocument() {
  if (!state.selectedDocument) {
    setStatus(documentStatus, 'Select a document first.', 'error');
    return;
  }
  const response = await apiFetch(`/admin/api/knowledge-base/documents/${encodeURIComponent(state.selectedDocument)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: documentEditor.value }),
  });
  const data = await response.json();
  if (!response.ok) {
    setStatus(documentStatus, data.detail || 'Unable to save document.', 'error');
    return;
  }
  setStatus(documentStatus, `${data.message}. Refresh the index to apply it to search.`, 'success');
  await loadKnowledgeBase();
}

async function deleteDocument() {
  if (!state.selectedDocument) {
    setStatus(documentStatus, 'Select a document first.', 'error');
    return;
  }
  const confirmed = window.confirm(`Delete ${state.selectedDocument}?`);
  if (!confirmed) {
    return;
  }
  const response = await apiFetch(`/admin/api/knowledge-base/documents/${encodeURIComponent(state.selectedDocument)}`, {
    method: 'DELETE',
  });
  const data = await response.json();
  if (!response.ok) {
    setStatus(documentStatus, data.detail || 'Unable to delete document.', 'error');
    return;
  }
  documentName.value = '';
  documentEditor.value = '';
  state.selectedDocument = null;
  setStatus(documentStatus, `${data.message}. Refresh the index to remove it from search.`, 'success');
  await loadKnowledgeBase();
}

async function uploadDocument() {
  const input = document.getElementById('documentUpload');
  const file = input.files && input.files[0];
  if (!file) {
    setStatus(documentStatus, 'Choose a document to upload.', 'error');
    return;
  }
  const formData = new FormData();
  formData.append('file', file);
  const response = await apiFetch('/admin/api/knowledge-base/documents', {
    method: 'POST',
    body: formData,
  });
  const data = await response.json();
  if (!response.ok) {
    setStatus(documentStatus, data.detail || 'Unable to upload document.', 'error');
    return;
  }
  input.value = '';
  setStatus(documentStatus, `${data.message}. Refresh the index to include it in search.`, 'success');
  await loadKnowledgeBase();
  await loadDocument(data.name);
}

async function refreshKnowledgeBase() {
  const response = await apiFetch('/admin/api/knowledge-base/refresh', { method: 'POST' });
  const data = await response.json();
  if (!response.ok) {
    setStatus(documentStatus, data.detail || 'Unable to refresh knowledge base.', 'error');
    return;
  }
  lastRefresh.textContent = formatDate(data.status?.last_refreshed_at);
  setStatus(documentStatus, `${data.message}. Indexed ${data.status?.indexed_files?.length || 0} files.`, 'success');
  await loadKnowledgeBase();
}

document.getElementById('reloadPrompts').addEventListener('click', () => loadPrompts());
document.getElementById('savePrompt').addEventListener('click', savePrompt);
document.getElementById('uploadDocument').addEventListener('click', uploadDocument);
document.getElementById('saveDocument').addEventListener('click', saveDocument);
document.getElementById('deleteDocument').addEventListener('click', deleteDocument);
document.getElementById('refreshKnowledgeBase').addEventListener('click', refreshKnowledgeBase);

Promise.all([loadPrompts(), loadKnowledgeBase()]).catch((error) => {
  console.error(error);
  setStatus(promptStatus, 'Unable to load admin data.', 'error');
  setStatus(documentStatus, 'Unable to load admin data.', 'error');
});