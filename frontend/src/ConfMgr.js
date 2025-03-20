import React, { useState, useEffect, useRef } from 'react';
import Settings from './Settings';
import { AgGridReact } from '@ag-grid-community/react';
import { ClientSideRowModelModule } from '@ag-grid-community/client-side-row-model';
import { ModuleRegistry } from '@ag-grid-community/core';
import '@ag-grid-community/styles/ag-grid.css';
import '@ag-grid-community/styles/ag-theme-alpine.css';
import './ConfMgr.css';

// Register the required modules
ModuleRegistry.registerModules([ClientSideRowModelModule]);

const ConfMgr = () => {
  const [showSettings, setShowSettings] = useState(false);
  const [unmatchedData, setUnmatchedData] = useState([]);
  const [matchedData, setMatchedData] = useState([]);
  const [emailMatchData, setEmailMatchData] = useState([]);
  const [filterModel, setFilterModel] = useState(null);
  const [settings, setSettings] = useState({
    syncFilters: true
  });
  const [selectedTradeId, setSelectedTradeId] = useState(null);
  const [selectedTradeData, setSelectedTradeData] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [floatingMessage, setFloatingMessage] = useState('');
  const [floatingPosition, setFloatingPosition] = useState({ x: 0, y: 0 });
  const [isFloatingVisible, setIsFloatingVisible] = useState(false);
  const [isBottomGridExpanded, setIsBottomGridExpanded] = useState(false);
    
  // Use refs for tracking interaction state to avoid render cycles
  const isFilterActiveRef = useRef(false);
  const lastInteractionTimeRef = useRef(Date.now());
  const INTERACTION_THRESHOLD = 30000; // 30 seconds
  
  // References to the grid APIs
  const matchedGridRef = useRef(null);
  const emailGridRef = useRef(null);
  const unmatchedGridRef = useRef(null);

  // Add these state variables for the context menu
  const [contextMenuPosition, setContextMenuPosition] = useState({ x: 0, y: 0 });
  const [showContextMenu, setShowContextMenu] = useState(false);
  const [selectedEmailRow, setSelectedEmailRow] = useState(null);

  // Updated column definitions to match your JSON structure
  const columnDefs = [
    { headerName: 'Trade Number', field: 'TradeNumber', width: 70, sortable: true, filter: true },
    { headerName: 'Counterparty', field: 'CounterpartyName', width: 180, sortable: true, filter: true },
    { headerName: 'Product Type', field: 'ProductType', width: 120, sortable: true, filter: true },
    { 
      headerName: 'Value Date', 
      field: 'ValueDate', 
      width: 120,
      sortable: true, 
      filter: true,
      valueFormatter: params => {
        if (!params.value) return '';
        const [day, month, year] = params.value.split('-');
        const date = new Date(year, month - 1, day);
        const dayName = date.toLocaleDateString('es-CL', { weekday: 'short' });
        return `${dayName} ${day}-${month}-${year}`;
      }
    },
    { headerName: 'Buyer', field: 'Buyer', width: 100, sortable: true, filter: true },
    { headerName: 'Seller', field: 'Seller', width: 100, sortable: true, filter: true },
    { headerName: 'Currency 1', field: 'Currency1', width: 90, sortable: true, filter: true },
    { headerName: 'Amount 1', field: 'QuantityCurrency1', width: 100, sortable: true, filter: true, valueFormatter: params => params.value.toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }) },
    { headerName: 'Forward Price', field: 'ForwardPrice', width: 110, sortable: true, filter: true, valueFormatter: params => params.value.toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }) },
    { headerName: 'Currency 2', field: 'Currency2', width: 90, sortable: true, filter: true },
    { 
      headerName: 'Amount 2', 
      field: 'QuantityCurrency2', 
      width: 100, 
      sortable: true, 
      filter: true, 
      valueFormatter: params => params.value !== null ? params.value.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      }) : 'N/A' // Return 'N/A' for null values
    },
    { 
      headerName: 'Maturity Date', 
      field: 'MaturityDate', 
      width: 120,
      sortable: true, 
      filter: true,
      valueFormatter: params => {
        if (!params.value) return '';
        const [day, month, year] = params.value.split('-');
        const date = new Date(year, month - 1, day);
        const dayName = date.toLocaleDateString('en-US', { weekday: 'short' });
        return `${dayName} ${day}-${month}-${year}`;
      }
    },
    { headerName: 'Fixing Reference', field: 'FixingReference', width: 100, sortable: true, filter: true },
    { headerName: 'Settlement Type', field: 'SettlementType', width: 100, sortable: true, filter: true },
    { headerName: 'Settlement Currency', field: 'SettlementCurrency', width: 100, sortable: true, filter: true },
    { 
      headerName: 'Payment Date', 
      field: 'PaymentDate', 
      width: 120,
      sortable: true, 
      filter: true,
      valueFormatter: params => {
        if (!params.value) return '';
        const [day, month, year] = params.value.split('-');
        const date = new Date(year, month - 1, day);
        const dayName = date.toLocaleDateString('en-US', { weekday: 'short' });
        return `${dayName} ${day}-${month}-${year}`;
      }
    },
    { headerName: 'Counterparty Payment Method', field: 'CounterpartyPaymentMethod', width: 100, sortable: true, filter: true },
    { headerName: 'Bank Payment Method', field: 'BankPaymentMethod', width: 100, sortable: true, filter: true },
  ];

  // Column definitions for the left grid (matched trades)
  const tradeColumnDefs = [
    { headerName: 'Trade Number', field: 'TradeNumber', width: 70 },
    { headerName: 'Counterparty Name', field: 'CounterpartyName', width: 150 },
    { headerName: 'Product Type', field: 'ProductType', width: 120 },
    { 
      headerName: 'Value Date', 
      field: 'ValueDate', 
      width: 120,
      sortable: true, 
      filter: true,
      valueFormatter: params => {
        if (!params.value) return '';
        const [day, month, year] = params.value.split('-');
        const date = new Date(year, month - 1, day);
        const dayName = date.toLocaleDateString('es-CL', { weekday: 'short' });
        return `${dayName} ${day}-${month}-${year}`;
      }
    },
    { headerName: 'Buyer', field: 'Buyer', width: 120 },
    { headerName: 'Seller', field: 'Seller', width: 120 },
    { headerName: 'Currency 1', field: 'Currency1', width: 100 },
    { 
      headerName: 'Amount Currency 1', 
      field: 'QuantityCurrency1', 
      width: 140,
      valueFormatter: params => params.value.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      })
    },
    { 
      headerName: 'Forward Price', 
      field: 'ForwardPrice', 
      width: 100,
      valueFormatter: params => params.value.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      })
    },
    { headerName: 'Currency 2', field: 'Currency2', width: 100 },
    { 
      headerName: 'Amount Currency 2', 
      field: 'QuantityCurrency2', 
      width: 140,
      valueFormatter: params => params.value.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      })
    },
    { 
      headerName: 'Maturity Date', 
      field: 'MaturityDate', 
      width: 120,
      sortable: true, 
      filter: true,
      valueFormatter: params => {
        if (!params.value) return '';
        const [day, month, year] = params.value.split('-');
        const date = new Date(year, month - 1, day);
        const dayName = date.toLocaleDateString('es-CL', { weekday: 'short' });
        return `${dayName} ${day}-${month}-${year}`;
      }
    },
    { headerName: 'Fixing Reference', field: 'FixingReference', width: 140 },
    { headerName: 'Settlement Type', field: 'SettlementType', width: 130 },
    { headerName: 'Settlement Currency', field: 'SettlementCurrency', width: 140 },
    { 
      headerName: 'Payment Date', 
      field: 'PaymentDate', 
      width: 120,
      sortable: true, 
      filter: true,
      valueFormatter: params => {
        if (!params.value) return '';
        const [day, month, year] = params.value.split('-');
        const date = new Date(year, month - 1, day);
        const dayName = date.toLocaleDateString('es-CL', { weekday: 'short' });
        return `${dayName} ${day}-${month}-${year}`;
      }
    },
    { headerName: 'Counterparty Payment Method', field: 'CounterpartyPaymentMethod', width: 200 },
    { headerName: 'Bank Payment Method', field: 'BankPaymentMethod', width: 160 }
  ];

  // First, modify the getRowStatus function to use the status field from the data
  const getRowStatus = (params) => {
    // If the row has a status field, use it
    if (params.data.status) {
      return params.data.status;
    }
    
    // Fallback to the old logic if status is not available
    // Check if row is an unrecognized trade
    if (params.data.ProductType === 'Not a recognized trade') {
      return 'Unrecognized';
    }

    // Find the corresponding trade in matchedData
    const matchedTrade = matchedData.find(trade => trade.TradeNumber === params.data.InferredTradeID);
    
    if (matchedTrade) {
      // Compare all relevant fields between email data and matched trade
      const fieldsToCompare = [
        'CounterpartyName',
        'ProductType',
        'ValueDate',
        'Buyer',
        'Seller',
        'Currency1',
        'QuantityCurrency1',
        'ForwardPrice',
        'Currency2',
        'QuantityCurrency2',
        'MaturityDate',
        'FixingReference',
        'SettlementType',
        'SettlementCurrency',
        'PaymentDate',
        'CounterpartyPaymentMethod',
        'BankPaymentMethod'
      ];

      const hasDifferences = fieldsToCompare.some(field => {
        return params.data[field] !== matchedTrade[field];
      });

      return hasDifferences ? 'Difference' : 'Confirmation OK';
    }

    return 'Unrecognized';
  };

  // Modify your email column definitions
  const emailColumnDefs = [
    { headerName: 'Inferred Trade Number', field: 'InferredTradeID', width: 80 },
    {
      headerName: 'Status',
      field: 'status',
      width: 110,
      sortable: true,
      filter: true,
      // Use valueGetter as a fallback if status field is not present
      valueGetter: params => params.data.status || getRowStatus(params),
      cellRenderer: params => {
        const status = params.value;
        let style = {};
        
        switch(status) {
          case 'Confirmation OK':
            style = { color: '#4CAF50', fontWeight: 'bold' };
            break;
          case 'Difference':
            style = { color: '#ff4444', fontWeight: 'bold' };
            break;
          case 'Unrecognized':
            style = { color: '#FFFFFF', fontWeight: 'bold' };
            break;
          case 'Resolved':
            style = { color: '#00e7ff', fontWeight: 'bold' };
            break;
          case 'Tagged':
            style = { color: '#FB9205', fontWeight: 'bold' };
            break;
        }
        
        return <div style={style}>{status}</div>;
      }
    },
    { headerName: 'Email Sender', field: 'EmailSender', width: 150 },
    { headerName: 'Email Date', field: 'EmailDate', width: 120 },
    { headerName: 'Email Time', field: 'EmailTime', width: 120 },
    { headerName: 'Email Subject', field: 'EmailSubject', width: 200 },
    { 
      headerName: 'Counterparty Name', 
      field: 'CounterpartyName', 
      width: 150,
      cellClassRules: {
        'mismatch-cell': params => {
          if (!selectedTradeData || !params.data.InferredTradeID) return false;
          return params.data.InferredTradeID === selectedTradeId && 
                 params.data.CounterpartyName !== selectedTradeData.CounterpartyName;
        }
      }
    },
    { 
      headerName: 'Product Type', 
      field: 'ProductType', 
      width: 120,
      cellClassRules: {
        'mismatch-cell': params => {
          if (!selectedTradeData || !params.data.InferredTradeID) return false;
          return params.data.InferredTradeID === selectedTradeId && 
                 params.data.ProductType !== selectedTradeData.ProductType;
        }
      }
    },
    { 
      headerName: 'Value Date', 
      field: 'ValueDate', 
      width: 120,
      sortable: true, 
      filter: true,
      valueFormatter: params => {
        if (!params.value) return '';
        const [day, month, year] = params.value.split('-');
        const date = new Date(year, month - 1, day);
        const dayName = date.toLocaleDateString('es-CL', { weekday: 'short' });
        return `${dayName} ${day}-${month}-${year}`;
      },
      cellClassRules: {
        'mismatch-cell': params => {
          if (!selectedTradeData || !params.data.InferredTradeID) return false;
          return params.data.InferredTradeID === selectedTradeId && 
                 params.data.ValueDate !== selectedTradeData.ValueDate;
        }
      }
    },
    { 
      headerName: 'Buyer', 
      field: 'Buyer', 
      width: 120,
      cellClassRules: {
        'mismatch-cell': params => {
          if (!selectedTradeData || !params.data.InferredTradeID) return false;
          return params.data.InferredTradeID === selectedTradeId && 
                 params.data.Buyer !== selectedTradeData.Buyer;
        }
      }
    },
    { 
      headerName: 'Seller', 
      field: 'Seller', 
      width: 120,
      cellClassRules: {
        'mismatch-cell': params => {
          if (!selectedTradeData || !params.data.InferredTradeID) return false;
          return params.data.InferredTradeID === selectedTradeId && 
                 params.data.Seller !== selectedTradeData.Seller;
        }
      }
    },
    { 
      headerName: 'Currency 1', 
      field: 'Currency1', 
      width: 100,
      cellClassRules: {
        'mismatch-cell': params => {
          if (!selectedTradeData || !params.data.InferredTradeID) return false;
          return params.data.InferredTradeID === selectedTradeId && 
                 params.data.Currency1 !== selectedTradeData.Currency1;
        }
      }
    },
    { 
      headerName: 'Amount Currency 1', 
      field: 'QuantityCurrency1', 
      width: 140,
      valueFormatter: params => params.value.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      }),
      cellClassRules: {
        'mismatch-cell': params => {
          if (!selectedTradeData || !params.data.InferredTradeID) return false;
          return params.data.InferredTradeID === selectedTradeId && 
                 params.data.QuantityCurrency1 !== selectedTradeData.QuantityCurrency1;
        }
      }
    },
    { 
      headerName: 'Forward Price', 
      field: 'ForwardPrice', 
      width: 120,
      valueFormatter: params => params.value.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      }),
      cellClassRules: {
        'mismatch-cell': params => {
          if (!selectedTradeData || !params.data.InferredTradeID) return false;
          return params.data.InferredTradeID === selectedTradeId && 
                 params.data.ForwardPrice !== selectedTradeData.ForwardPrice;
        }
      }
    },
    { 
      headerName: 'Currency 2', 
      field: 'Currency2', 
      width: 100,
      cellClassRules: {
        'mismatch-cell': params => {
          if (!selectedTradeData || !params.data.InferredTradeID) return false;
          return params.data.InferredTradeID === selectedTradeId && 
                 params.data.Currency2 !== selectedTradeData.Currency2;
        }
      }
    },
    { 
      headerName: 'Amount Currency 2', 
      field: 'QuantityCurrency2', 
      width: 140,
      valueFormatter: params => params.value !== null ? params.value.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      }) : 'N/A', // Return 'N/A' for null values,
      cellClassRules: {
        'mismatch-cell': params => {
          if (!selectedTradeData || !params.data.InferredTradeID) return false;
          return params.data.InferredTradeID === selectedTradeId && 
                 params.data.QuantityCurrency2 !== selectedTradeData.QuantityCurrency2;
        }
      }
    },
    { 
      headerName: 'Maturity Date', 
      field: 'MaturityDate', 
      width: 120,
      valueFormatter: params => {
        if (!params.value) return '';
        const [day, month, year] = params.value.split('-');
        const date = new Date(year, month - 1, day);
        const dayName = date.toLocaleDateString('es-CL', { weekday: 'short' });
        return `${dayName} ${day}-${month}-${year}`;
      },
      cellClassRules: {
        'mismatch-cell': params => {
          if (!selectedTradeData || !params.data.InferredTradeID) return false;
          return params.data.InferredTradeID === selectedTradeId && 
                 params.data.MaturityDate !== selectedTradeData.MaturityDate;
        }
      }
    },
    { 
      headerName: 'Fixing Reference', 
      field: 'FixingReference', 
      width: 140,
      cellClassRules: {
        'mismatch-cell': params => {
          if (!selectedTradeData || !params.data.InferredTradeID) return false;
          return params.data.InferredTradeID === selectedTradeId && 
                 params.data.FixingReference !== selectedTradeData.FixingReference;
        }
      }
    },
    { 
      headerName: 'Settlement Type', 
      field: 'SettlementType', 
      width: 130,
      cellClassRules: {
        'mismatch-cell': params => {
          if (!selectedTradeData || !params.data.InferredTradeID) return false;
          return params.data.InferredTradeID === selectedTradeId && 
                 params.data.SettlementType !== selectedTradeData.SettlementType;
        }
      }
    },
    { 
      headerName: 'Settlement Currency', 
      field: 'SettlementCurrency', 
      width: 140,
      cellClassRules: {
        'mismatch-cell': params => {
          if (!selectedTradeData || !params.data.InferredTradeID) return false;
          return params.data.InferredTradeID === selectedTradeId && 
                 params.data.SettlementCurrency !== selectedTradeData.SettlementCurrency;
        }
      }
    },
    { 
      headerName: 'Payment Date', 
      field: 'PaymentDate', 
      width: 120,
      valueFormatter: params => {
        if (!params.value) return '';
        const [day, month, year] = params.value.split('-');
        const date = new Date(year, month - 1, day);
        const dayName = date.toLocaleDateString('es-CL', { weekday: 'short' });
        return `${dayName} ${day}-${month}-${year}`;
      },
      cellClassRules: {
        'mismatch-cell': params => {
          if (!selectedTradeData || !params.data.InferredTradeID) return false;
          return params.data.InferredTradeID === selectedTradeId && 
                 params.data.PaymentDate !== selectedTradeData.PaymentDate;
        }
      }
    },
    { 
      headerName: 'Counterparty Payment Method', 
      field: 'CounterpartyPaymentMethod', 
      width: 200,
      cellClassRules: {
        'mismatch-cell': params => {
          if (!selectedTradeData || !params.data.InferredTradeID) return false;
          return params.data.InferredTradeID === selectedTradeId && 
                 params.data.CounterpartyPaymentMethod !== selectedTradeData.CounterpartyPaymentMethod;
        }
      }
    },
    { 
      headerName: 'Bank Payment Method', 
      field: 'BankPaymentMethod', 
      width: 160,
      cellClassRules: {
        'mismatch-cell': params => {
          if (!selectedTradeData || !params.data.InferredTradeID) return false;
          return params.data.InferredTradeID === selectedTradeId && 
                 params.data.BankPaymentMethod !== selectedTradeData.BankPaymentMethod;
        }
      }
    }
  ];

  // Simple utility function to update interaction time without state changes
  const updateInteractionTime = () => {
    lastInteractionTimeRef.current = Date.now();
  };

  const loadData = async () => {
    if (isRefreshing) return;

    setIsRefreshing(true);
    try {
      // Load all data in parallel
      const [unmatchedResponse, matchedResponse, emailMatchResponse] = await Promise.all([
        fetch('../assets/unmatched_trades.json'),
        fetch('../assets/matched_trades.json'),
        fetch('../assets/email_matches.json')
      ]);

      const [unmatched, matched, emailMatches] = await Promise.all([
        unmatchedResponse.json(),
        matchedResponse.json(),
        emailMatchResponse.json()
      ]);

      setUnmatchedData(unmatched);
      setMatchedData(matched);
      setEmailMatchData(emailMatches);

    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setIsRefreshing(false);
    }
  };

  // Initial data load
  useEffect(() => {
    loadData();
  }, []);

  // Function to handle filter changes from any grid
  const onFilterChanged = (params) => {
    if (!settings.syncFilters) return; // Skip synchronization if disabled
    
    // Only sync if the filter was "applied" (not during typing)
    if (!params.api.isDestroyed() && params.api.getFilterModel) {
      const newModel = params.api.getFilterModel();
      setFilterModel(newModel);
      
      // Apply filter to all grids except the source grid
      [matchedGridRef, emailGridRef, unmatchedGridRef].forEach(gridRef => {
        if (gridRef.current && gridRef.current.api !== params.api) {
          gridRef.current.api.setFilterModel(newModel);
        }
      });
    }
  };

  const onGridReady = (params, gridRef) => {
    if (gridRef) {
      gridRef.current = params;
    }
    
    // Setup event listeners for filter activity tracking
    if (params.api) {
      // Use AG Grid's event system instead of DOM events
      params.api.addEventListener('filterChanged', () => {
        updateInteractionTime();
        // Set filter as active when filter changes
        isFilterActiveRef.current = true;
        
        // Allow time for the filter to be fully applied
        setTimeout(() => {
          isFilterActiveRef.current = false;
        }, 500);
      });
      
      params.api.addEventListener('filterModified', () => {
        updateInteractionTime();
        isFilterActiveRef.current = true;
      });
    }
  }

  const buttonBaseStyle = {
    background: 'none',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    padding: '8px 16px',
    fontSize: '10px',
    fontWeight: 'bold',
    display: 'flex',
    alignItems: 'center',
    gap: '5px',
    transition: 'opacity 0.2s',
    fontFamily: 'Manrope, sans-serif',
  };

  // Default column definitions with better filter behavior
  const defaultColDef = {
    sortable: true,
    filter: true,
    resizable: true,
    headerClass: 'small-header',
    filterParams: {
      buttons: ['apply', 'reset'],
      closeOnApply: true,
      suppressAndOrCondition: true,
    }
  };

  // Function to handle row clicks in matched deals grid
  const onMatchedRowClicked = (params) => {
    const clickedTradeId = params.data.TradeNumber;
    setSelectedTradeId(clickedTradeId);
    setSelectedTradeData(params.data);
    updateInteractionTime();
    
    // Force both unmatched and email grids to resort
    [unmatchedGridRef, emailGridRef].forEach(gridRef => {
      if (gridRef.current && gridRef.current.api) {
        const api = gridRef.current.api;
        
        // Sort by TradeNumber/InferredTradeID to bring selected row to top
        api.applyColumnState({
          state: [{
            colId: gridRef === emailGridRef ? 'InferredTradeID' : 'TradeNumber',
            sort: 'asc',
          }],
          defaultState: { sort: null }
        });
        
        // Redraw the rows
        api.redrawRows();
      }
    });
  };

  // Function to handle row clicks in email grid
  const onEmailRowClicked = (params) => {
    const clickedTradeId = params.data.InferredTradeID;
    setSelectedTradeId(clickedTradeId);
    
    // Find and set the corresponding matched trade data
    const matchedTrade = matchedData.find(trade => trade.TradeNumber === clickedTradeId);
    setSelectedTradeData(matchedTrade || params.data);
    
    updateInteractionTime();
    
    // Force both unmatched and matched grids to resort
    [unmatchedGridRef, matchedGridRef].forEach(gridRef => {
      if (gridRef.current && gridRef.current.api) {
        const api = gridRef.current.api;
        api.applyColumnState({
          state: [{
            colId: 'TradeNumber',
            sort: 'asc',
          }],
          defaultState: { sort: null }
        });
        api.redrawRows();
      }
    });
  };

  // Setup document-level click handler to detect when user clicks outside the grid
  useEffect(() => {
    const handleDocumentClick = (e) => {
      // Find grid elements using class names
      const gridContainers = document.querySelectorAll('.ag-theme-alpine-dark');
      let clickedInsideGrid = false;
      
      gridContainers.forEach(container => {
        if (container.contains(e.target)) {
          clickedInsideGrid = true;
        }
      });
      
      // If clicked outside all grids, reset filter active state
      if (!clickedInsideGrid) {
        setTimeout(() => {
          isFilterActiveRef.current = false;
        }, 200);
      }
    };
    
    document.addEventListener('click', handleDocumentClick);
    return () => document.removeEventListener('click', handleDocumentClick);
  }, []);

  // Grid props using refs for interaction tracking
  const gridProps = {
    onFilterChanged: (params) => {
      updateInteractionTime();
      onFilterChanged(params);
    },
    onSortChanged: () => {
      updateInteractionTime();
    },
    onCellClicked: () => {
      updateInteractionTime();
    },
    onRowClicked: () => {
      updateInteractionTime();
    },
    onFirstDataRendered: () => {
      // Do nothing - no need to manipulate state here
    },
    onGridReady: onGridReady,
    onCellValueChanged: () => {
      updateInteractionTime();
    },
    onColumnResized: () => {
      updateInteractionTime();
    },
    onPaginationChanged: () => {
      updateInteractionTime();
    }
  };

  const clearMatchedTrades = async () => {
    if (window.confirm('Are you sure you want to clear all matched trades?')) {
      try {
        await fetch('../api/clear-matched-trades', { method: 'POST' });
        loadData(); // Refresh the data after clearing
      } catch (error) {
        console.error('Error clearing matched trades:', error);
      }
    }
  };

  const clearEmailMatches = async () => {
    if (window.confirm('Are you sure you want to clear all email matches?')) {
      try {
        await fetch('../api/clear-email-matches', { method: 'POST' });
        loadData(); // Refresh the data after clearing
      } catch (error) {
        console.error('Error clearing email matches:', error);
      }
    }
  };

  useEffect(() => {
    const handleClickOutside = () => {
      setIsFloatingVisible(false); // Hide the floating label
    };
  
    document.addEventListener('click', handleClickOutside);
    return () => {
      document.removeEventListener('click', handleClickOutside);
    };
  }, []);

  // Handle right-click on email grid cells
  const handleEmailCellRightClick = (params) => {
    params.event.preventDefault();
    
    // Only show context menu for status column
    if (params.column.colId === 'status') {
      setSelectedEmailRow(params.node);
      setContextMenuPosition({
        x: params.event.clientX,
        y: params.event.clientY
      });
      setShowContextMenu(true);
    } else {
      // Show email body for other columns
      const emailBody = params.data.EmailBody;
      const emailSubject = params.data.EmailSubject;
      if (emailBody) {
        setFloatingMessage(
          <div>
            <strong>{emailSubject}</strong>
            <br />
            {emailBody}
          </div>
        );
        setFloatingPosition({
          x: Math.min(params.event.clientX, window.innerWidth - 300),
          y: Math.max(30, params.event.clientY - 30),
        });
        setIsFloatingVisible(true);
      }
    }
  };

  // Add this useEffect to handle clicks outside the context menu
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (showContextMenu && event.target.closest('.context-menu') === null) {
        setShowContextMenu(false);
      }
    };

    document.addEventListener('click', handleClickOutside);
    return () => {
      document.removeEventListener('click', handleClickOutside);
    };
  }, [showContextMenu]);

  // Handle status change from context menu
  const handleStatusChange = async (newStatus) => {
    if (selectedEmailRow) {
      console.log('Changing status to:', newStatus);
      
      try {
        // Get the email ID from the selected row
        const emailId = selectedEmailRow.data.InferredTradeID;
        
        let response, result;
        
        if (newStatus === 'Undo') {
          // Call the undo endpoint
          response = await fetch('http://localhost:5005/undo-status-change', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              emailId: emailId
            }),
          });
        } else {
          // Call the regular update endpoint
          response = await fetch('http://localhost:5005/update-email-status', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              emailId: emailId,
              status: newStatus
            }),
          });
        }
        
        if (!response.ok) {
          throw new Error(`Failed to ${newStatus === 'Undo' ? 'undo status change' : 'update status'}: ${response.status} ${response.statusText}`);
        }
        
        result = await response.json();
        console.log(`${newStatus === 'Undo' ? 'Status undo' : 'Status update'} result:`, result);
        
        // Check if the operation was successful
        if (!result.success) {
          // Show an alert with the error message from the backend
          alert(`Operation failed: ${result.message}`);
        } else {
          // Refresh the data to show the updated status
          loadData();
        }
      } catch (error) {
        console.error('Error updating status:', error);
        // Show a user-friendly error message
        alert(`Error: ${error.message || 'An unknown error occurred'}`);
      }
      
      // Close the context menu
      setShowContextMenu(false);
    }
  };

  // Add this function to handle clearing JSON files
  const handleClearJsonFile = async (fileType) => {
    // Show a confirmation dialog
    const confirmMessage = fileType === 'email_matches' 
      ? 'Are you sure you want to clear all email matches? This action cannot be undone.'
      : 'Are you sure you want to clear all matched trades? This action cannot be undone.';
    
    if (!window.confirm(confirmMessage)) {
      return; // User cancelled the operation
    }
    
    try {
      const response = await fetch('http://localhost:5005/clear-json-file', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          fileType: fileType
        }),
      });
      
      if (!response.ok) {
        throw new Error(`Failed to clear ${fileType}: ${response.status} ${response.statusText}`);
      }
      
      const result = await response.json();
      console.log(`Clear ${fileType} result:`, result);
      
      // Check if the operation was successful
      if (!result.success) {
        // Show an alert with the error message from the backend
        alert(`Operation failed: ${result.message}`);
      } else {
        // Show success message
        alert(result.message);
        // Refresh the data to reflect the changes
        loadData();
      }
    } catch (error) {
      console.error(`Error clearing ${fileType}:`, error);
      // Show a user-friendly error message
      alert(`Error: ${error.message || 'An unknown error occurred'}`);
    }
  };

  return (
    <div style={{
      backgroundColor: 'black',
      color: 'white',
      height: '100vh',
      fontFamily: 'Manrope, sans-serif',
      display: 'flex',
      flexDirection: 'column',
      overflowX: 'hidden',
      maxWidth: '100vw',
      padding: '20px',
      boxSizing: 'border-box',
    }}>
      {/* Top Section with buttons */}
      <div style={{
        width: '100%',
        height: '60px',
        padding: '10px',
        backgroundColor: '#1a1a1a',
        borderBottom: '1px solid #00e7ff',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        overflow: 'visible',
        position: 'relative',
        zIndex: 10,
      }}>
        <img src="palace_blanco.png" alt="Logo" style={{ height: '40px', marginRight: '10px' }} />
        
        <div style={{
          display: 'flex',
          gap: '10px',
          marginLeft: 'auto',
          marginRight: '10px',
        }}>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <span
              onClick={loadData}
              style={{
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '30px',
                height: '30px',
                borderRadius: '50%',
                backgroundColor: 'transparent',
                transition: 'opacity 0.3s, transform 0.2s',
                opacity: 0.7,
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.opacity = '1';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.opacity = '0.7';
              }}
              onMouseDown={(e) => {
                e.currentTarget.style.transform = 'scale(0.85)';
              }}
              onMouseUp={(e) => {
                e.currentTarget.style.transform = 'scale(1)';
              }}
              title="Refresh"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#00e7ff"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ width: '20px', height: '20px' }}
              >
                <polyline points="23 4 23 10 17 10"></polyline>
                <polyline points="1 20 1 14 7 14"></polyline>
                <path d="M3.51 9a9 9 0 0 1 14.36-3.36L23 10M1 14l5.63 5.36A9 9 0 0 0 20.49 15"></path>
              </svg>
            </span>
          </div>
          
        </div>

        <button
          onClick={() => {
            updateInteractionTime();
            setShowSettings(true);
          }}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: '#00e7ff',
            fontSize: '20px',
          }}
        >
          ⚙️
        </button>
      </div>

      {/* Upper section with two grids - now with dynamic height */}
      <div style={{ 
        display: 'flex', 
        gap: '20px', 
        height: isBottomGridExpanded ? '45vh' : '80vh', 
        marginBottom: '20px',
        transition: 'height 0.3s ease-in-out'
      }}>
        {/* Left Grid - Matched Deals */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {/* Probable Murex Matches Header */}
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
            <h3 style={{ 
              color: 'white', 
              marginBottom: '0px', 
              fontSize: '14px',
              display: 'flex', 
              alignItems: 'baseline',
              padding: '10px'
            }}>
              Probable Murex Matches:
            </h3>
            <button
              onClick={() => handleClearJsonFile('matched_trades')}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: '#ff4444',
                fontSize: '16px',
                padding: 0,
                display: 'inline-flex',
                alignItems: 'baseline',
                marginLeft: '-6px',
                position: 'relative',
                top: '1px'
              }}
              title="Clear all matched trades"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#00e7ff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{ width: '12px', height: '12px' }}>
                <path d="M3 6h18" />
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
                <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              </svg>
            </button>
          </div>
          <div className="ag-theme-alpine-dark" style={{ 
            flex: 1,
            width: '100%',
            border: '1px solid #00e7ff',
            borderRadius: '4px',
            fontSize: '12px',
          }}>
            <AgGridReact
              {...gridProps}
              ref={matchedGridRef}
              modules={[ClientSideRowModelModule]}
              columnDefs={tradeColumnDefs}
              rowData={matchedData}
              onGridReady={(params) => onGridReady(params, matchedGridRef)}
              onFilterChanged={onFilterChanged}
              defaultColDef={{
                ...defaultColDef,
                sortable: true,
                comparator: (valueA, valueB, nodeA, nodeB, isInverted, colDef) => {
                  // First check for selected row
                  const aIsSelected = nodeA.data.TradeNumber === selectedTradeId;
                  const bIsSelected = nodeB.data.TradeNumber === selectedTradeId;

                  if (aIsSelected) return -1;
                  if (bIsSelected) return 1;

                  // If neither is selected, do normal string/number comparison
                  if (valueA == null) return valueB == null ? 0 : 1;
                  if (valueB == null) return -1;
                  
                  // Handle numbers
                  if (typeof valueA === 'number' && typeof valueB === 'number') {
                    return valueA - valueB;
                  }
                  
                  // Handle strings
                  return valueA < valueB ? -1 : valueA > valueB ? 1 : 0;
                }
              }}
              rowHeight={25}
              headerHeight={30}
              onRowClicked={onMatchedRowClicked}
              rowClassRules={{
                'selected-row': params => params.data.TradeNumber === selectedTradeId,
                'highlight-difference': params => {
                  // Find corresponding email match
                  const emailMatch = emailMatchData.find(email => email.InferredTradeID === params.data.TradeNumber);
                  if (!emailMatch) return false;

                  // Compare relevant fields
                  const fieldsToCompare = [
                    'Currency1',
                    'QuantityCurrency1',
                    'ForwardPrice',
                    'Currency2',
                    'QuantityCurrency2',
                    'MaturityDate',
                    'FixingReference',
                    'SettlementType',
                    'SettlementCurrency',
                    'PaymentDate',
                    'CounterpartyPaymentMethod',
                    'BankPaymentMethod'
                  ];

                  return fieldsToCompare.some(field => params.data[field] !== emailMatch[field]);
                }
              }}
            />
          </div>

        </div>

        {/* Right Grid - Email Match */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {/* Email Data Header */}
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
            <h3 style={{ 
              color: 'white', 
              marginBottom: '0px', 
              fontSize: '14px',
              display: 'flex', 
              alignItems: 'baseline',
              padding: '10px'
            }}>
              Email Data:
            </h3>
            <button
              onClick={() => handleClearJsonFile('email_matches')}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: '#ff4444',
                fontSize: '16px',
                padding: 0,
                display: 'inline-flex',
                alignItems: 'baseline',
                marginLeft: '-6px',
                position: 'relative',
                top: '1px'
              }}
              title="Clear all email matches"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#00e7ff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{ width: '12px', height: '12px' }}>
                <path d="M3 6h18" />
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
                <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              </svg>
            </button>
          </div>
          <div className="ag-theme-alpine-dark" style={{ 
            flex: 1,
            width: '100%',
            border: '1px solid #00e7ff',
            borderRadius: '4px',
            fontSize: '12px',
          }}>
            <AgGridReact
              {...gridProps}
              ref={emailGridRef}
              modules={[ClientSideRowModelModule]}
              columnDefs={emailColumnDefs}
              rowData={emailMatchData}
              onGridReady={(params) => onGridReady(params, emailGridRef)}
              onFilterChanged={onFilterChanged}
              onRowClicked={onEmailRowClicked}
              onCellContextMenu={handleEmailCellRightClick}
              defaultColDef={{
                ...defaultColDef,
                sortable: true,
                comparator: (valueA, valueB, nodeA, nodeB) => {
                  const aIsSelected = nodeA.data.InferredTradeID === selectedTradeId;
                  const bIsSelected = nodeB.data.InferredTradeID === selectedTradeId;

                  if (aIsSelected) return -1;
                  if (bIsSelected) return 1;
                  return 0;
                }
              }}
              rowHeight={25}
              headerHeight={30}
              rowClassRules={{
                'selected-row': params => params.data.InferredTradeID === selectedTradeId,
                'highlight-row': params => params.data.ProductType === 'Not a recognized trade'
              }}
            />
          </div>
        </div>
      </div>

      {/* Bottom Grid - Unmatched Trades - now collapsible */}
      <div style={{ 
        height: isBottomGridExpanded ? '45vh' : '40px',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
        transition: 'height 0.3s ease-in-out',
        border: '1px solid #00e7ff',
        borderRadius: '4px',
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '0 10px',
          height: '40px',
          cursor: 'pointer',
          backgroundColor: '#1a1a1a',
        }}
        onClick={() => setIsBottomGridExpanded(!isBottomGridExpanded)}
        >
          <h3 style={{ 
            color: 'white', 
            margin: 0,
            fontSize: '14px',
            display: 'flex', 
            alignItems: 'center' 
          }}>
            Murex Data
          </h3>
          <span style={{
            color: '#00e7ff',
            fontSize: '20px',
            fontWeight: 'bold',
          }}>
            {isBottomGridExpanded ? '−' : '+'}
          </span>
        </div>
        
        <div style={{ 
          flex: 1,
          display: isBottomGridExpanded ? 'block' : 'none',
          transition: 'all 0.3s ease-in-out'
        }}>
          <div className="ag-theme-alpine-dark" style={{ 
            height: '100%',
            width: '100%',
            fontSize: '12px',
          }}>
            <AgGridReact
              {...gridProps}
              ref={unmatchedGridRef}
              modules={[ClientSideRowModelModule]}
              columnDefs={columnDefs}
              rowData={unmatchedData}
              pagination={true}
              paginationPageSize={20}
              onGridReady={(params) => onGridReady(params, unmatchedGridRef)}
              onFilterChanged={onFilterChanged}
              defaultColDef={{
                ...defaultColDef,
                sortable: true,
                comparator: (valueA, valueB, nodeA, nodeB) => {
                  const aIsSelected = nodeA.data.TradeNumber === selectedTradeId;
                  const bIsSelected = nodeB.data.TradeNumber === selectedTradeId;

                  if (aIsSelected) return -1;
                  if (bIsSelected) return 1;
                  return 0;
                }
              }}
              rowHeight={25}
              headerHeight={30}
              rowClassRules={{
                'selected-row': params => {
                  const isSelected = params.data.TradeNumber === selectedTradeId;
                  return isSelected;
                }
              }}
              getRowId={(params) => params.data.TradeNumber.toString()}
            />
          </div>
        </div>
      </div>

      {/* Settings Modal */}
      {showSettings && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <Settings 
            onClose={() => setShowSettings(false)}
            settings={settings}
            onSettingsChange={setSettings}
          />
        </div>
      )}

      {showContextMenu && (
        <div
          className="context-menu"
          style={{
            position: 'fixed',
            left: contextMenuPosition.x,
            top: contextMenuPosition.y,
            backgroundColor: '#1a1a1a',
            border: '1px solid #00e7ff',
            borderRadius: '4px',
            padding: '5px',
            zIndex: 1000,
          }}
        >
          <div
            onClick={() => handleStatusChange('Resolved')}
            style={{
              padding: '8px 12px',
              cursor: 'pointer',
              color: 'white',
              fontSize: '12px',
            }}
          >
            Resolved
          </div>
          <div
            onClick={() => handleStatusChange('Tagged')}
            style={{
              padding: '8px 12px',
              cursor: 'pointer',
              color: 'white',
              fontSize: '12px',
            }}
          >
            Tagged
          </div>
          <div
            onClick={() => handleStatusChange('Undo')}
            style={{
              padding: '8px 12px',
              cursor: 'pointer',
              color: 'white',
              fontSize: '12px',
              borderTop: '1px solid #333',
              marginTop: '5px',
              paddingTop: '8px',
            }}
          >
            Undo
          </div>
        </div>
      )}

      {isFloatingVisible && (
        <div 
          className="floating-message"
          style={{
            position: 'fixed',
            left: floatingPosition.x,
            top: floatingPosition.y,
            backgroundColor: '#00e7ff', // Electric blue background
            color: 'black', // Black text
            padding: '5px 10px',
            borderRadius: '5px',
            boxShadow: '0 2px 4px rgba(0, 0, 0, 0.2)', // Optional subtle shadow
            fontSize: '12px',
            border: '1px solid #ccc',
            zIndex: 1000,
            pointerEvents: 'none', // Make it non-interactive
            maxWidth: '300px',
            wordWrap: 'break-word'
          }}
        >
          {floatingMessage}
        </div>
      )}
    </div>
  );
};

export default ConfMgr;