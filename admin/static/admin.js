const state = {
  selectedPromptId: null,
  selectedDocument: null,
  selectedConversationId: null,
  chatPhone: '',
  isChatOpen: false,
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
const toggleChatPanelButton = document.getElementById('toggleChatPanel');
const restartApplicationButton = document.getElementById('restartApplication');
const adminChatPanel = document.getElementById('adminChatPanel');
const chatPhone = document.getElementById('chatPhone');
const startChatSessionButton = document.getElementById('startChatSession');
const chatSessionBadge = document.getElementById('chatSessionBadge');
const chatLog = document.getElementById('chatLog');
const chatMessage = document.getElementById('chatMessage');
const sendChatMessageButton = document.getElementById('sendChatMessage');
const chatStatus = document.getElementById('chatStatus');
const conversationSearch = document.getElementById('conversationSearch');
const conversationList = document.getElementById('conversationList');
const conversationIdBadge = document.getElementById('conversationIdBadge');
const conversationUpdated = document.getElementById('conversationUpdated');
const conversationUserData = document.getElementById('conversationUserData');
const conversationTranscript = document.getElementById('conversationTranscript');
const conversationStatus = document.getElementById('conversationStatus');
const clearConversationButton = document.getElementById('clearConversation');

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

function escapeHtml(value) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function toggleChatPanel(forceOpen) {
  state.isChatOpen = typeof forceOpen === 'boolean' ? forceOpen : !state.isChatOpen;
  adminChatPanel.hidden = !state.isChatOpen;
  toggleChatPanelButton.textContent = state.isChatOpen ? 'Hide Chat' : 'Open Chat';
  toggleChatPanelButton.setAttribute('aria-expanded', String(state.isChatOpen));
}

function renderChatEmptyState() {
  chatLog.innerHTML = '<div class="chat-empty">Start a session to send messages with the existing chat backend.</div>';
}

function appendChatMessage(role, message) {
  if (chatLog.querySelector('.chat-empty')) {
    chatLog.innerHTML = '';
  }
  const item = document.createElement('div');
  item.className = `chat-message ${role}`;
  item.innerHTML = `<span>${role === 'user' ? 'You' : 'Assistant'}</span><p>${escapeHtml(message)}</p>`;
  chatLog.appendChild(item);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function setChatSession(phone) {
  state.chatPhone = phone;
  chatPhone.value = phone;
  chatSessionBadge.textContent = phone ? `Session ${phone}` : 'Session not started';
}

function startChatSession() {
  const phone = chatPhone.value.trim();
  if (!phone) {
    setStatus(chatStatus, 'Enter a phone number to start the chat session.', 'error');
    return;
  }
  setChatSession(phone);
  renderChatEmptyState();
  setStatus(chatStatus, `Chat session ready for ${phone}.`, 'success');
}

async function sendChatMessage() {
  const phone = state.chatPhone || chatPhone.value.trim();
  const message = chatMessage.value.trim();
  if (!phone) {
    setStatus(chatStatus, 'Start a chat session first.', 'error');
    return;
  }
  if (!message) {
    setStatus(chatStatus, 'Type a message before sending.', 'error');
    return;
  }

  setChatSession(phone);
  appendChatMessage('user', message);
  chatMessage.value = '';
  setStatus(chatStatus, 'Waiting for assistant response...');

  try {
    const response = await apiFetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone, ask: message }),
    });
    const data = await response.json();
    if (!response.ok) {
      setStatus(chatStatus, data.detail || 'Unable to send chat message.', 'error');
      return;
    }
    appendChatMessage('assistant', data.answer || 'No response received.');
    setStatus(chatStatus, 'Response received.', 'success');
  } catch (error) {
    console.error(error);
    setStatus(chatStatus, 'Unable to reach the chat service.', 'error');
  }
}

async function apiFetch(url, options) {
  const response = await fetch(url, options);
  if (response.status === 401) {
    window.location.href = '/admin/login';
    throw new Error('Unauthorized');
  }
  return response;
}

async function restartApplication() {
  const confirmed = window.confirm('Restart the FastAPI application now?');
  if (!confirmed) {
    return;
  }

  restartApplicationButton.disabled = true;
  restartApplicationButton.textContent = 'Restarting...';
  setStatus(promptStatus, 'Restarting application...', '');

  try {
    const response = await apiFetch('/admin/api/restart', { method: 'POST' });
    const data = await response.json();
    if (!response.ok) {
      setStatus(promptStatus, data.detail || 'Unable to restart application.', 'error');
      return;
    }
    setStatus(promptStatus, `${data.message}. The page may disconnect briefly.`, 'success');
    window.setTimeout(() => window.location.reload(), 3000);
  } catch (error) {
    console.error(error);
    setStatus(promptStatus, 'Unable to restart application.', 'error');
  } finally {
    window.setTimeout(() => {
      restartApplicationButton.disabled = false;
      restartApplicationButton.textContent = 'Restart App';
    }, 3000);
  }
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

function renderConversationList(items) {
  conversationList.innerHTML = '';

  if (!items.length) {
    conversationList.innerHTML = '<div class="list-item"><strong>No cached conversations</strong><small>Try a different phone number search or wait for new traffic.</small></div>';
    return;
  }

  for (const item of items) {
    const row = document.createElement('div');
    row.className = `list-item ${state.selectedConversationId === item.conversation_id ? 'active' : ''}`.trim();
    row.innerHTML = `<strong>${escapeHtml(item.conversation_id)}</strong><small>${item.message_count} messages</small><small>Updated ${formatDate(item.last_message_at)}</small><small>${escapeHtml(item.preview || 'No messages yet.')}</small>`;
    row.addEventListener('click', () => loadConversation(item.conversation_id));
    conversationList.appendChild(row);
  }
}

function renderConversationDetails(data) {
  state.selectedConversationId = data?.conversation_id || null;
  conversationIdBadge.textContent = data?.conversation_id || 'Select a conversation';
  conversationUpdated.textContent = data?.last_message_at ? `Last updated ${formatDate(data.last_message_at)}` : '';
  clearConversationButton.disabled = !data?.conversation_id;

  const userData = data?.user_data && Object.keys(data.user_data).length
    ? JSON.stringify(data.user_data, null, 2)
    : 'No user data available.';
  conversationUserData.textContent = userData;

  if (!data?.messages?.length) {
    conversationTranscript.innerHTML = '<div class="chat-empty">Select a cached conversation to inspect its history.</div>';
    return;
  }

  conversationTranscript.innerHTML = data.messages.map((message) => `
    <div class="chat-message ${message.role === 'user' ? 'user' : 'assistant'}">
      <span>${escapeHtml(message.role || 'unknown')}</span>
      <p>${escapeHtml(message.content || '')}</p>
      <small>${formatDate(message.timestamp)}</small>
    </div>
  `).join('');
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

async function loadConversations(searchValue = conversationSearch.value.trim()) {
  const query = searchValue ? `?search=${encodeURIComponent(searchValue)}` : '';
  const response = await apiFetch(`/admin/api/conversations${query}`);
  const data = await response.json();
  if (!response.ok) {
    setStatus(conversationStatus, data.detail || 'Unable to load cached conversations.', 'error');
    return;
  }

  renderConversationList(data.items || []);

  if (!state.selectedConversationId) {
    renderConversationDetails(data.selected || null);
    renderConversationList(data.items || []);
  } else if (!(data.items || []).some((item) => item.conversation_id === state.selectedConversationId)) {
    renderConversationDetails(data.selected || null);
    renderConversationList(data.items || []);
  }

  setStatus(conversationStatus, '', '');
}

async function loadConversation(conversationId) {
  state.selectedConversationId = conversationId;
  const response = await apiFetch(`/admin/api/conversations/${encodeURIComponent(conversationId)}`);
  const data = await response.json();
  if (!response.ok) {
    setStatus(conversationStatus, data.detail || 'Unable to load conversation.', 'error');
    return;
  }

  renderConversationDetails(data);
  await loadConversations(conversationSearch.value.trim());
}

async function clearConversation() {
  if (!state.selectedConversationId) {
    setStatus(conversationStatus, 'Select a conversation first.', 'error');
    return;
  }

  const confirmed = window.confirm(`Clear cached history for ${state.selectedConversationId}?`);
  if (!confirmed) {
    return;
  }

  const response = await apiFetch(`/admin/api/conversations/${encodeURIComponent(state.selectedConversationId)}`, {
    method: 'DELETE',
  });
  const data = await response.json();
  if (!response.ok) {
    setStatus(conversationStatus, data.detail || 'Unable to clear conversation.', 'error');
    return;
  }

  state.selectedConversationId = null;
  renderConversationDetails(null);
  setStatus(conversationStatus, data.message || 'Conversation cleared.', 'success');
  await loadConversations(conversationSearch.value.trim());
}

document.getElementById('reloadPrompts').addEventListener('click', () => loadPrompts());
document.getElementById('savePrompt').addEventListener('click', savePrompt);
document.getElementById('uploadDocument').addEventListener('click', uploadDocument);
document.getElementById('saveDocument').addEventListener('click', saveDocument);
document.getElementById('deleteDocument').addEventListener('click', deleteDocument);
document.getElementById('refreshKnowledgeBase').addEventListener('click', refreshKnowledgeBase);
document.getElementById('searchConversations').addEventListener('click', () => loadConversations(conversationSearch.value.trim()));
document.getElementById('reloadConversations').addEventListener('click', () => loadConversations(conversationSearch.value.trim()));
document.getElementById('clearConversation').addEventListener('click', clearConversation);
toggleChatPanelButton.addEventListener('click', () => toggleChatPanel());
restartApplicationButton.addEventListener('click', restartApplication);
startChatSessionButton.addEventListener('click', startChatSession);
sendChatMessageButton.addEventListener('click', sendChatMessage);
chatMessage.addEventListener('keydown', (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
    event.preventDefault();
    sendChatMessage();
  }
});
conversationSearch.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    event.preventDefault();
    loadConversations(conversationSearch.value.trim());
  }
});

toggleChatPanel(false);
renderConversationDetails(null);

Promise.all([loadPrompts(), loadKnowledgeBase(), loadConversations()]).catch((error) => {
  console.error(error);
  setStatus(promptStatus, 'Unable to load admin data.', 'error');
  setStatus(documentStatus, 'Unable to load admin data.', 'error');
  setStatus(conversationStatus, 'Unable to load admin data.', 'error');
});