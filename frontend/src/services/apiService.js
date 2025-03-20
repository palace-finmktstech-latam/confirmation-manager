// src/services/apiService.js
const API_BASE_URL = 'http://localhost:5005';

export const fetchAllData = async () => {
  try {
    // Load all data in parallel
    const [unmatchedResponse, matchedResponse, emailMatchResponse] = await Promise.all([
      fetch('./assets/unmatched_trades.json'),
      fetch('./assets/matched_trades.json'),
      fetch('./assets/email_matches.json')
    ]);

    const [unmatched, matched, emailMatches] = await Promise.all([
      unmatchedResponse.json(),
      matchedResponse.json(),
      emailMatchResponse.json()
    ]);

    return { unmatched, matched, emailMatches };
  } catch (error) {
    console.error('Error fetching data:', error);
    throw error;
  }
};

export const updateEmailStatus = async (emailId, status) => {
  try {
    const response = await fetch(`${API_BASE_URL}/update-email-status`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ emailId, status }),
    });
    
    if (!response.ok) {
      throw new Error(`Failed to update status: ${response.status} ${response.statusText}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error updating status:', error);
    throw error;
  }
};

export const undoStatusChange = async (emailId) => {
  try {
    const response = await fetch(`${API_BASE_URL}/undo-status-change`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ emailId }),
    });
    
    if (!response.ok) {
      throw new Error(`Failed to undo status change: ${response.status} ${response.statusText}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error undoing status change:', error);
    throw error;
  }
};

export const clearJsonFile = async (fileType) => {
  try {
    const response = await fetch(`${API_BASE_URL}/clear-json-file`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ fileType }),
    });
    
    if (!response.ok) {
      throw new Error(`Failed to clear ${fileType}: ${response.status} ${response.statusText}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error(`Error clearing ${fileType}:`, error);
    throw error;
  }
};