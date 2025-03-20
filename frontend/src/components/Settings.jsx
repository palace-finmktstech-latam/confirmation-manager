import React, { useState } from 'react';

const Settings = ({ onClose, settings, onSettingsChange }) => {
  const [myName, setMyName] = useState('');
  const [myEntity, setMyEntity] = useState('');

  const inputStyle = {
    backgroundColor: '#2d2d2d',
    border: '1px solid #444',
    borderRadius: '4px',
    color: 'white',
    padding: '6px 8px',
    fontSize: '10px',
    width: '100%',
    boxSizing: 'border-box',
  };

  const labelStyle = {
    display: 'block',
    fontSize: '10px',
    marginBottom: '4px',
    color: '#888',
  };

  return (
    <div
      style={{
        backgroundColor: '#1c1c1c',
        color: 'white',
        fontFamily: 'Manrope, sans-serif',
        borderRadius: '8px',
        padding: '15px',
        position: 'relative',
        border: '1px solid #00e7ff',
        width: '300px',
        maxWidth: '90%',
        margin: '0 auto',
        maxHeight: '80vh',
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      <button
        onClick={onClose}
        style={{
          position: 'absolute',
          top: '4px',
          right: '4px',
          background: 'none',
          border: 'none',
          color: '#00e7ff',
          fontSize: '14px',
          cursor: 'pointer',
          padding: '2px',
        }}
        aria-label="Close"
      >
        ✖
      </button>

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '15px',
          flexShrink: 0
        }}
      >
        <img
          src="palace_blanco.png"
          alt="Palace Logo"
          style={{ height: '20px' }}
        />
        <h1 style={{ fontSize: '12px', margin: 0 }}>Settings</h1>
      </div>

      <div style={{
        overflowY: 'auto',
        flexGrow: 1,
        marginRight: '-8px',
        paddingRight: '8px'
      }}>
        <div style={{ 
          marginBottom: '15px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '10px'
        }}>
          <span style={{ 
            color: 'white', 
            fontSize: '12px'
          }}>
            Synchronize Filters Across Grids
          </span>
          <div
            style={{
              position: 'relative',
              width: '50px',
              height: '24px',
              backgroundColor: settings.syncFilters ? '#00e7ff' : '#ccc',
              borderRadius: '12px',
              cursor: 'pointer',
              transition: 'background-color 0.3s',
              flexShrink: 0
            }}
            onClick={() => onSettingsChange({
              ...settings,
              syncFilters: !settings.syncFilters
            })}
          >
            <div
              style={{
                position: 'absolute',
                top: '2px',
                left: settings.syncFilters ? '26px' : '2px',
                width: '20px',
                height: '20px',
                backgroundColor: 'white',
                borderRadius: '50%',
                transition: 'left 0.3s',
              }}
            />
          </div>
        </div>
      </div>

      <button
        onClick={onClose}
        style={{
          padding: '6px 12px',
          backgroundColor: '#0077cc',
          color: 'white',
          border: 'none',
          borderRadius: '4px',
          fontSize: '12px',
          fontWeight: 'bold',
          cursor: 'pointer',
          width: '100%',
          flexShrink: 0
        }}
      >
        Save Settings
      </button>
    </div>
  );
};

export default Settings;