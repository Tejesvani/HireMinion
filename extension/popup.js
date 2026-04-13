const resumeSelect = document.getElementById('resumeSelect');
const progressContainer = document.getElementById('progressContainer');
const progressText = document.getElementById('progressText');
const spinner = document.getElementById('spinner');

let resumes = [];

// === PERSISTENCE ===
function saveState() {
  chrome.storage.local.set({
    ui: {
      selectedResume: resumeSelect.value
    }
  });
}

async function loadState() {
  const { ui } = await chrome.storage.local.get('ui');
  if (!ui) return;
  if (ui.selectedResume) {
    resumeSelect.value = ui.selectedResume;
  }
}
// === END PERSISTENCE ===

function showProgress(message = 'Processing...') {
  progressContainer.style.display = 'block';
  progressContainer.className = '';
  spinner.style.display = 'block';
  progressText.textContent = message;
}

function showError(message) {
  progressContainer.style.display = 'block';
  progressContainer.className = 'error';
  spinner.style.display = 'none';
  progressText.textContent = message;
}

function showSuccess(message = 'Complete!') {
  progressContainer.style.display = 'block';
  progressContainer.className = 'success';
  spinner.style.display = 'none';
  progressText.textContent = message;
}

function hideProgress() {
  progressContainer.style.display = 'none';
}

function setButtons(disabled) {
  document.querySelectorAll('button').forEach(btn => btn.disabled = disabled);
}

// Extract filename from full path
function getFileName(path) {
  if (!path) return null;
  // Handle both forward and backslashes
  return path.split(/[/\\]/).pop();
}

// === HELPER FUNCTIONS ===
function showBlock(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = 'block';
}

function hideBlock(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = 'none';
}

function showJobBanner(text) {
  document.getElementById('banner-text').innerText = text;
  document.getElementById('job-banner').style.display = 'flex';
  const genBtn = document.getElementById('generate-btn');
  if (genBtn) genBtn.disabled = false;
}

function updateCharCount(counterId, length, limit) {
  const el = document.getElementById(counterId);
  if (!el) return;
  el.innerText = `${length}/${limit}`;
  el.classList.toggle('over', length > limit);
}

function updateWordCount(counterId, text) {
  const el = document.getElementById(counterId);
  if (!el) return;
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  el.innerText = `${words} words`;
}

function renderCoverLetter(cover) {
  if (!cover) return;
  const parts = [];
  if (cover.recipient) parts.push(`Dear ${cover.recipient},`);
  if (Array.isArray(cover.paragraphs) && cover.paragraphs.length) {
    parts.push(...cover.paragraphs);
  }
  if (cover.closing) parts.push(cover.closing);
  const text = parts.join('\n\n');
  if (!text.trim()) return;
  document.getElementById('cover-text').innerText = text;
  showBlock('block-cover');
}

function anyBlockVisible() {
  return ['block-resume','block-cover','block-connection','block-inmail','block-qa']
    .some(id => {
      const el = document.getElementById(id);
      return el && el.style.display !== 'none';
    });
}

function getPDFName() {
  // Read from the resume file dropdown
  return resumeSelect.value.replace(/\.tex$/i, '');
}

// === SESSION RESTORE ===
async function restoreSession() {
  try {
    const res = await fetch('http://localhost:8000/api/status');
    if (!res.ok) return;
    const status = await res.json();

    if (status.has_job_details && status.job_details) {
      const jd = status.job_details;
      showJobBanner(`${jd.role || 'Role'} @ ${jd.company || 'Company'}`);
    }

    if (status.has_tailored_resume) {
      const pdfName = getPDFName();
      document.getElementById('resume-pdf-link').href =
        `http://localhost:8000/api/download-pdf/${pdfName}.pdf?t=${Date.now()}`;
      showBlock('block-resume');
    }

    if (status.has_tailored_cover && status.tailored_cover) {
      renderCoverLetter(status.tailored_cover);
    }

    if (status.has_connection_request && status.connection_request) {
      const msg = status.connection_request.message || '';
      document.getElementById('connection-text').innerText = msg;
      updateCharCount('connection-char-count', msg.length, 300);
      showBlock('block-connection');
    }

    if (status.has_inmail && status.inmail) {
      document.getElementById('inmail-subject').innerText = status.inmail.subject || '';
      document.getElementById('inmail-text').innerText = status.inmail.message || '';
      updateWordCount('inmail-word-count', status.inmail.message || '');
      showBlock('block-inmail');
    }

    if (anyBlockVisible()) {
      document.getElementById('results-area').style.display = 'block';
    }

  } catch (e) {
    console.log('[HireMinion] Backend not reachable on restore:', e.message);
  }
}

// === POPULATE RESULTS ===
async function populateResults(apiResponse) {
  document.getElementById('results-area').style.display = 'block';

  // Resume PDF link
  if (apiResponse.pdf_path) {
    const pdfName = getPDFName() + '.pdf';
    document.getElementById('resume-pdf-link').href =
      `http://localhost:8000/api/download-pdf/${pdfName}?t=${Date.now()}`;
    showBlock('block-resume');
  }

  // Fetch full status to get structured JSON for text blocks
  try {
    const statusRes = await fetch('http://localhost:8000/api/status');
    const status = await statusRes.json();

    if (status.tailored_cover) {
      renderCoverLetter(status.tailored_cover);
    }

    if (status.connection_request && status.connection_request.message) {
      const msg = status.connection_request.message;
      document.getElementById('connection-text').innerText = msg;
      updateCharCount('connection-char-count', msg.length, 300);
      showBlock('block-connection');
    }

    if (status.inmail && status.inmail.message) {
      document.getElementById('inmail-subject').innerText =
        status.inmail.subject || '';
      document.getElementById('inmail-text').innerText =
        status.inmail.message;
      updateWordCount('inmail-word-count', status.inmail.message);
      showBlock('block-inmail');
    }

    if (status.job_details) {
      const jd = status.job_details;
      showJobBanner(`${jd.role || ''} @ ${jd.company || ''}`);
    }

  } catch (e) {
    console.log('[HireMinion] Could not fetch status after pipeline:', e.message);
  }
}

// === CLEAR SESSION ===
async function clearSession() {
  try {
    await fetch('http://localhost:8000/api/clear', { method: 'DELETE' });
  } catch (e) {
    console.log('[HireMinion] Clear failed:', e.message);
  }

  // Hide all result blocks
  ['block-resume','block-cover','block-connection',
   'block-inmail','block-qa'].forEach(hideBlock);

  document.getElementById('results-area').style.display = 'none';
  document.getElementById('job-banner').style.display = 'none';
  const genBtn = document.getElementById('generate-btn');
  if (genBtn) genBtn.disabled = true;
  document.getElementById('qa-question').value = '';
  document.getElementById('qa-answer-text').innerText = '';
  document.getElementById('cover-text').innerText = '';
  document.getElementById('connection-text').innerText = '';
  document.getElementById('inmail-subject').innerText = '';
  document.getElementById('inmail-text').innerText = '';
  updateCharCount('connection-char-count', 0, 300);
  updateWordCount('inmail-word-count', '');
}

// Q&A checkbox toggle
document.getElementById('feat-qa').addEventListener('change', function() {
  document.getElementById('qa-input-area').style.display =
    this.checked ? 'block' : 'none';
});

// Save on changes
resumeSelect.addEventListener('change', saveState);

// Fetch available resumes on load
async function loadResumes() {
  try {
    const response = await fetch('http://localhost:8000/api/list-resumes');
    const data = await response.json();
    if (data.success && data.resumes.length > 0) {
      resumes = data.resumes;
      resumeSelect.innerHTML = '<option value="">Select a resume...</option>';
      resumes.forEach(r => {
        const option = document.createElement('option');
        option.value = r;
        option.textContent = r.replace('.tex', '');
        resumeSelect.appendChild(option);
      });
    } else {
      resumeSelect.innerHTML = '<option value="">No resumes found</option>';
    }
  } catch (e) {
    console.error('Failed to load resumes:', e);
    resumeSelect.innerHTML = '<option value="">Failed to load resumes</option>';
  }
}

// Start Scrape & Run Pipeline
document.getElementById('scrapeBtn').addEventListener('click', async () => {
  // Validate resume selection (required)
  const selectedResume = resumeSelect.value;
  if (!selectedResume) {
    showError('Please select a resume');
    return;
  }

  const options = {
    resume: document.getElementById('feat-resume').checked,
    coverLetter: document.getElementById('feat-cover').checked,
    resumeFile: selectedResume,
    connectionRequest: document.getElementById('feat-connection').checked,
    inmail: document.getElementById('feat-inmail').checked,
    customPrompt: null
  };

  setButtons(true);
  showProgress('Processing...');

  try {
    const response = await chrome.runtime.sendMessage({ action: 'scrape', options });
    console.log('[HireMinion] Pipeline response:', response);

    if (response.success) {
      let generatedFiles = [];

      // Resume PDF
      if (response.pdf_path) {
        const pdfName = getFileName(response.pdf_path);
        generatedFiles.push(`📄 ${pdfName}`);
      }

      // Cover Letter PDF
      if (response.cover_pdf_path) {
        const coverName = getFileName(response.cover_pdf_path);
        generatedFiles.push(`✉️ ${coverName}`);
      }

      // Show generated files in status
      let statusMsg = 'Complete!';
      if (generatedFiles.length > 0) {
        statusMsg = `Generated: ${generatedFiles.join(', ')}`;
      }
      showSuccess(statusMsg);

      await populateResults(response);
    } else {
      showError(response.error || response.message || 'Unknown error');
      if (response.error_details) {
        document.getElementById('qa-answer-text').innerText = response.error_details;
        showBlock('block-qa');
        document.getElementById('results-area').style.display = 'block';
      }
    }
  } catch (e) {
    showError('Connection failed');
  }

  setButtons(false);
});

// Generate-only (no re-scrape)
document.getElementById('generate-btn').addEventListener('click', async function() {
  try {
    const statusRes = await fetch('http://localhost:8000/api/status');
    const status = await statusRes.json();
    if (!status.has_job_details) {
      alert('No job loaded. Please click Scrape on a job posting first.');
      return;
    }
  } catch (e) {
    alert('Cannot reach backend. Is the server running on port 8000?');
    return;
  }

  const origText = this.innerText;
  this.disabled = true;
  this.innerText = '⏳ Generating...';

  const options = {
    resume:            document.getElementById('feat-resume').checked,
    coverLetter:       document.getElementById('feat-cover').checked,
    connectionRequest: document.getElementById('feat-connection').checked,
    inmail:            document.getElementById('feat-inmail').checked,
  };

  try {
    const res = await fetch('http://localhost:8000/api/generate-only', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ options })
    });
    const data = await res.json();
    console.log('[HireMinion] Generate-only response:', data);
    if (data.success) {
      await populateResults(data);
    } else {
      alert('Error: ' + (data.error || 'Generation failed'));
    }
  } catch (e) {
    alert('Request failed: ' + e.message);
  } finally {
    this.disabled = false;
    this.innerText = origText;
  }
});

// Retrieve Custom Output
document.getElementById('retrieveBtn').addEventListener('click', async () => {
  setButtons(true);
  showProgress('Retrieving...');

  try {
    const response = await fetch('http://localhost:8000/api/retrieve-output');
    const data = await response.json();

    if (data.success) {
      showSuccess('Retrieved!');
      document.getElementById('qa-answer-text').innerText = data.content;
      showBlock('block-qa');
      document.getElementById('results-area').style.display = 'block';
    } else {
      showError(data.error || 'No output found');
    }
  } catch (e) {
    showError('Connection failed');
  }

  setButtons(false);
});

// Store Information - Mark as applied
document.getElementById('storeBtn').addEventListener('click', async () => {
  const selectedResume = resumeSelect.value;
  if (!selectedResume) {
    showError('Please select a resume');
    return;
  }

  setButtons(true);
  showProgress('Marking as applied...');

  try {
    // First try to mark as applied directly
    const response = await fetch('http://localhost:8000/api/mark-applied', {
      method: 'POST'
    });
    const data = await response.json();

    if (data.success) {
      showSuccess(`Marked as applied! ${data.company} | ${data.role}`);
    } else if (data.not_found || data.no_metadata) {
      // URL not in archive or no metadata, need to scrape first
      showProgress('Scraping page first...');

      // Run scrape with all checkboxes off (just job details)
      const scrapeResponse = await chrome.runtime.sendMessage({
        action: 'scrape',
        options: {
          resume: false,
          resumeFile: selectedResume,
          coverLetter: false,
          customPrompt: null
        }
      });

      if (scrapeResponse.success) {
        // Now mark as applied
        const retryResponse = await fetch('http://localhost:8000/api/mark-applied', {
          method: 'POST'
        });
        const retryData = await retryResponse.json();

        if (retryData.success) {
          showSuccess(`Scraped & marked as applied! ${retryData.company} | ${retryData.role}`);
        } else {
          showError(retryData.error || 'Failed to mark as applied');
        }
      } else {
        showError(scrapeResponse.error || 'Failed to scrape page');
      }
    } else {
      showError(data.error || 'Failed to mark as applied');
    }
  } catch (e) {
    showError('Connection failed');
  }

  setButtons(false);
});

// Clear button
document.getElementById('clearBtn').addEventListener('click', async () => {
  setButtons(true);
  showProgress('Clearing...');
  await clearSession();
  showSuccess('Cleared all files');
  resumeSelect.value = '';
  chrome.storage.local.remove('ui');
  setButtons(false);
});

// Q&A answer button
document.getElementById('qa-answer-btn').addEventListener('click', async function() {
  const question = document.getElementById('qa-question').value.trim();
  if (!question) return;

  const origText = this.innerText;
  this.disabled = true;
  this.innerText = 'Answering...';

  try {
    const res = await fetch('http://localhost:8000/api/answer-question', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question })
    });
    const data = await res.json();

    if (data.success) {
      document.getElementById('qa-answer-text').innerText = data.answer;
      showBlock('block-qa');
      document.getElementById('results-area').style.display = 'block';
    } else {
      alert('Error: ' + (data.error || 'Unknown error'));
    }
  } catch (e) {
    alert('Could not reach backend. Is the server running on port 8000?');
  } finally {
    this.disabled = false;
    this.innerText = origText;
  }
});

// Delegated copy button listener
document.addEventListener('click', function(e) {
  const btn = e.target.closest('.copy-btn');
  if (!btn) return;
  const targetId = btn.getAttribute('data-target');
  if (!targetId) return;
  const text = document.getElementById(targetId)?.innerText || '';
  navigator.clipboard.writeText(text).then(() => {
    const orig = btn.innerText;
    btn.innerText = 'Copied ✓';
    setTimeout(() => { btn.innerText = orig; }, 1500);
  }).catch(() => {
    alert('Copy failed — try selecting and copying manually.');
  });
});

// Live counters on editable fields
document.getElementById('connection-text').addEventListener('input', function() {
  updateCharCount('connection-char-count', this.innerText.length, 300);
});

document.getElementById('inmail-text').addEventListener('input', function() {
  updateWordCount('inmail-word-count', this.innerText);
});

// Load resumes on popup open, then restore state and session
loadResumes().then(() => {
  loadState();
  restoreSession();
});
