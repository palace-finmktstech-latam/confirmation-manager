// src/contexts/AppContext.js
import React, { createContext, useState, useContext, useEffect } from 'react';
import { fetchAllData } from '../services/apiService';

const AppContext = createContext();

export const AppProvider = ({ children }) => {
  const [unmatchedData, setUnmatchedData] = useState([]);
  const [matchedData, setMatchedData] = useState([]);
  const [emailMatchData, setEmailMatchData] = useState([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [selectedTradeId, setSelectedTradeId] = useState(null);
  const [selectedTradeData, setSelectedTradeData] = useState(null);
  const [settings, setSettings] = useState({
    syncFilters: true
  });

  const loadData = async () => {
    if (isRefreshing) return;

    setIsRefreshing(true);
    try {
      const { unmatched, matched, emailMatches } = await fetchAllData();
      setUnmatchedData(unmatched);
      setMatchedData(matched);
      setEmailMatchData(emailMatches);
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setIsRefreshing(false);
    }
  };

  // Load data when component mounts
  useEffect(() => {
    loadData();
  }, []);

  return (
    <AppContext.Provider
      value={{
        unmatchedData,
        matchedData,
        emailMatchData,
        isRefreshing,
        selectedTradeId,
        selectedTradeData,
        settings,
        setSelectedTradeId,
        setSelectedTradeData,
        setSettings,
        loadData
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useAppContext = () => useContext(AppContext);