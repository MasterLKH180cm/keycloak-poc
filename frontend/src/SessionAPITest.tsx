import React, { useState, useEffect } from 'react';

interface Config {
  baseUrl: string;
  keycloakUrl: string;
  realm: string;
  clientId: string;
}

interface Responses {
  auth: string;
  study: string;
  ws: string;
  session: string;
  health: string;
}

interface ApiResponse {
  status: number;
  ok: boolean;
  data?: any;
  error?: string;
}

interface TokenData {
  access_token: string;
  timestamp: number;
}

export default function SessionAPITest() {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [config, setConfig] = useState<Config>({
    baseUrl: 'http://localhost:8000/session/api',
    keycloakUrl: 'https://20.168.120.11',
    realm: 'fastapi-realm',
    clientId: 'radiology-client'
  });
  const [studyId, setStudyId] = useState<string>('STUDY-12345');
  const [appType, setAppType] = useState<'viewer' | 'dictation'>('viewer');
  const [responses, setResponses] = useState<Responses>({
    auth: '',
    study: '',
    ws: '',
    session: '',
    health: ''
  });

  useEffect(() => {
    checkForOAuthCallback();
    loadStoredToken();
  }, []);

  const checkForOAuthCallback = (): void => {
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');
    const state = urlParams.get('state');
    const error = urlParams.get('error');
    const errorDescription = urlParams.get('error_description');
    
    if (error) {
      updateResponse('auth', `OAuth Error: ${error}\nDescription: ${errorDescription || 'No description provided'}`, 'error');
      window.history.replaceState({}, document.title, window.location.pathname);
      return;
    }
    
    if (code && state) {
      updateResponse('auth', `OAuth callback detected! Code: ${code.substring(0, 20)}...\nState: ${state.substring(0, 20)}...`, 'success');
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  };

  const loadStoredToken = (): void => {
    const stored = sessionStorage.getItem('keycloak_token');
    if (stored) {
      try {
        const tokenData: TokenData = JSON.parse(stored);
        setAccessToken(tokenData.access_token);
      } catch (e) {
        console.error('Failed to load stored token:', e);
      }
    }
  };

  const getHeaders = (): HeadersInit => {
    const headers: HeadersInit = { 'Content-Type': 'application/json' };
    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }
    return headers;
  };

  const makeRequest = async (
    endpoint: string, 
    method: string = 'GET', 
    body: any = null
  ): Promise<ApiResponse> => {
    try {
      const options: RequestInit = { method, headers: getHeaders() };
      if (body) options.body = JSON.stringify(body);
      
      const response = await fetch(config.baseUrl + endpoint, options);
      const data = await response.json();
      
      return { status: response.status, ok: response.ok, data };
    } catch (error) {
      return { 
        status: 0, 
        ok: false, 
        error: error instanceof Error ? error.message : 'Unknown error' 
      };
    }
  };

  const updateResponse = (
    key: keyof Responses, 
    data: any, 
    type: 'info' | 'success' | 'error' = 'info'
  ): void => {
    const formatted = typeof data === 'object' ? JSON.stringify(data, null, 2) : data;
    setResponses(prev => ({ ...prev, [key]: formatted }));
  };

  const initiateLogin = (): void => {
    const redirectUri = window.location.origin;
    const state = btoa(Math.random().toString()).replace(/[^a-zA-Z0-9]/g, '').substring(0, 32);
    sessionStorage.setItem('oauth_state', state);
    
    const authUrl = `${config.keycloakUrl}/realms/${config.realm}/protocol/openid-connect/auth?` +
      `client_id=${encodeURIComponent(config.clientId)}&` +
      `response_type=code&` +
      `scope=openid%20profile%20email&` +
      `redirect_uri=${encodeURIComponent(redirectUri)}&` +
      `state=${state}`;
    
    updateResponse('auth', 
      `Preparing OAuth redirect...\n\n` +
      `Current URL: ${window.location.href}\n` +
      `Redirect URI: ${redirectUri}\n` +
      `Keycloak URL: ${config.keycloakUrl}\n` +
      `Realm: ${config.realm}\n` +
      `Client ID: ${config.clientId}\n` +
      `State: ${state}\n\n` +
      `Full Auth URL: ${authUrl}\n\n` +
      `⚠️ IMPORTANT: Make sure this redirect URI is configured in Keycloak:\n` +
      `Admin Console → Clients → ${config.clientId} → Settings → Valid Redirect URIs\n` +
      `Add: ${redirectUri}/*\n\n` +
      `Redirecting in 3 seconds...`, 
      'success');
    
    setTimeout(() => { 
      updateResponse('auth', 'Redirecting to Keycloak now...', 'info');
      window.location.href = authUrl; 
    }, 3000);
  };

  const checkAuthStatus = (): void => {
    if (accessToken) {
      updateResponse('auth', {
        authenticated: true,
        token_preview: accessToken.substring(0, 50) + '...',
        message: 'Token present in storage'
      }, 'success');
    } else {
      updateResponse('auth', {
        authenticated: false,
        message: 'No token found. Please login.'
      }, 'error');
    }
  };

  const logout = (): void => {
    setAccessToken(null);
    sessionStorage.removeItem('keycloak_token');
    updateResponse('auth', 'Logged out locally. Token cleared.', 'success');
  };

  const openStudy = async (): Promise<void> => {
    if (!studyId) {
      updateResponse('study', 'Please enter a Study ID', 'error');
      return;
    }
    const result = await makeRequest(`/viewer/study_opened/${studyId}`, 'POST', {
      metadata: { source: 'test_page' }
    });
    updateResponse('study', result, result.ok ? 'success' : 'error');
  };

  const closeStudy = async (): Promise<void> => {
    if (!studyId) {
      updateResponse('study', 'Please enter a Study ID', 'error');
      return;
    }
    const result = await makeRequest(`/viewer/study_closed/${studyId}`, 'POST');
    updateResponse('study', result, result.ok ? 'success' : 'error');
  };

  const registerWebSocket = async (): Promise<void> => {
    const result = await makeRequest(`/open_websocket/${appType}`, 'POST', {
      client_info: { browser: navigator.userAgent }
    });
    updateResponse('ws', result, result.ok ? 'success' : 'error');
  };

  const getWebSocketStatus = async (): Promise<void> => {
    const result = await makeRequest(`/websocket_status/${appType}`);
    updateResponse('ws', result, result.ok ? 'success' : 'error');
  };

  const getActiveConnections = async (): Promise<void> => {
    const result = await makeRequest('/active_connections');
    updateResponse('ws', result, result.ok ? 'success' : 'error');
  };

  const getSessionState = async (): Promise<void> => {
    const result = await makeRequest('/get_session_state');
    updateResponse('session', result, result.ok ? 'success' : 'error');
  };

  const logoutUser = async (): Promise<void> => {
    const result = await makeRequest('/logout', 'POST');
    if (result.ok) {
      setAccessToken(null);
      sessionStorage.removeItem('keycloak_token');
    }
    updateResponse('session', result, result.ok ? 'success' : 'error');
  };

  const healthCheck = async (): Promise<void> => {
    const result = await makeRequest('/health');
    updateResponse('health', result, result.ok ? 'success' : 'error');
  };

  const updateConfig = (key: keyof Config, value: string): void => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-900 p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        {/* Animated Header */}
        <div className="text-center mb-8 animate-fade-in">
          <div className="card">
            <div className="bg-gradient-to-r from-purple-600 via-indigo-600 to-blue-600 text-white p-8 text-center relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-r from-purple-600/20 to-blue-600/20 animate-pulse-slow"></div>
              <div className="relative z-10">
                <h1 className="text-4xl md:text-5xl font-bold mb-4 text-shadow">
                  🔐 Session API & Login Test
                </h1>
                <p className="text-lg md:text-xl opacity-90 font-medium">
                  Comprehensive testing interface for Keycloak authentication and session management
                </p>
                <div className="flex justify-center mt-6">
                  <div className="flex items-center space-x-4">
                    <div className="w-3 h-3 bg-green-400 rounded-full animate-pulse"></div>
                    <span className="text-sm font-medium">API Testing Suite Active</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Configuration Section */}
        <div className="card mb-8 animate-fade-in">
          <div className="card-header">
            <h2 className="text-2xl font-bold text-gray-800 flex items-center">
              <span className="text-3xl mr-3">⚙️</span>
              Configuration Center
            </h2>
            <p className="text-gray-600 mt-2">Configure your API endpoints and authentication settings</p>
          </div>
          
          <div className="p-6">
            <div className="bg-gradient-to-r from-blue-50 to-indigo-50 p-6 rounded-xl border border-blue-200 mb-6">
              <h3 className="text-lg font-bold text-blue-800 mb-4 flex items-center">
                <span className="text-xl mr-2">🌐</span>
                API Configuration
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <label className="block text-sm font-bold text-gray-700">Base API URL</label>
                  <input
                    type="text"
                    value={config.baseUrl}
                    onChange={(e) => updateConfig('baseUrl', e.target.value)}
                    className="input-field"
                    placeholder="http://localhost:8000/session/api"
                  />
                </div>
                <div className="space-y-2">
                  <label className="block text-sm font-bold text-gray-700">Keycloak URL</label>
                  <input
                    type="text"
                    value={config.keycloakUrl}
                    onChange={(e) => updateConfig('keycloakUrl', e.target.value)}
                    className="input-field"
                    placeholder="https://your-keycloak-server"
                  />
                </div>
                <div className="space-y-2">
                  <label className="block text-sm font-bold text-gray-700">Realm</label>
                  <input
                    type="text"
                    value={config.realm}
                    onChange={(e) => updateConfig('realm', e.target.value)}
                    className="input-field"
                    placeholder="fastapi-realm"
                  />
                </div>
                <div className="space-y-2">
                  <label className="block text-sm font-bold text-gray-700">Client ID</label>
                  <input
                    type="text"
                    value={config.clientId}
                    onChange={(e) => updateConfig('clientId', e.target.value)}
                    className="input-field"
                    placeholder="radiology-client"
                  />
                </div>
              </div>
              <div className="mt-4 bg-yellow-50 p-4 rounded-lg border border-yellow-200">
                <p className="text-sm text-yellow-800 font-medium">
                  💡 <strong>Redirect URI:</strong> {window.location.origin}
                </p>
                <p className="text-xs text-yellow-700 mt-1">
                  This URI must be configured in Keycloak client settings under "Valid Redirect URIs"
                </p>
                <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded">
                  <p className="text-xs text-red-800 font-bold">🚨 SETUP REQUIRED:</p>
                  <p className="text-xs text-red-700 mt-1">
                    1. Go to Keycloak Admin Console<br/>
                    2. Navigate to: Clients → {config.clientId} → Settings<br/>
                    3. Add to "Valid Redirect URIs": <code className="bg-red-100 px-1 rounded">{window.location.origin}/*</code><br/>
                    4. Save the configuration
                  </p>
                </div>
              </div>
            </div>

            {/* Authentication Status */}
            <div className={`p-6 rounded-xl border-2 font-bold text-center transition-all duration-300 ${
              accessToken 
                ? 'bg-gradient-to-r from-green-50 to-emerald-50 border-green-300 text-green-800 glow-effect' 
                : 'bg-gradient-to-r from-red-50 to-pink-50 border-red-300 text-red-800'
            }`}>
              <div className="flex items-center justify-center space-x-3">
                <span className="text-2xl">{accessToken ? '🟢' : '🔴'}</span>
                <span className="text-lg">
                  {accessToken ? 'Authentication Active' : 'Authentication Required'}
                </span>
              </div>
              {accessToken && (
                <div className="mt-4 bg-white/50 backdrop-blur-sm rounded-lg p-3 border border-green-200">
                  <p className="text-xs text-green-700 font-mono break-all">
                    Token: {accessToken.substring(0, 60)}...
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Authentication Section */}
          <div className="card animate-fade-in">
            <div className="card-header">
              <h2 className="text-xl font-bold text-gray-800 flex items-center">
                <span className="text-2xl mr-3">🔑</span>
                Authentication Control
              </h2>
            </div>
            <div className="p-6">
              <div className="flex flex-wrap gap-3 mb-6">
                <button onClick={initiateLogin} className="btn-primary flex items-center space-x-2">
                  <span>🚀</span>
                  <span>Login with Keycloak</span>
                </button>
                <button onClick={logout} className="btn-danger flex items-center space-x-2">
                  <span>🚪</span>
                  <span>Logout</span>
                </button>
                <button onClick={checkAuthStatus} className="btn-info flex items-center space-x-2">
                  <span>🔍</span>
                  <span>Check Status</span>
                </button>
              </div>
              <div className="terminal p-4 rounded-lg max-h-80 overflow-y-auto whitespace-pre-wrap text-sm">
                {responses.auth || '🖥️  Authentication responses will appear here...\n\nWaiting for user action...'}
              </div>
            </div>
          </div>

          {/* Study Management Section */}
          <div className="card animate-fade-in">
            <div className="card-header">
              <h2 className="text-xl font-bold text-gray-800 flex items-center">
                <span className="text-2xl mr-3">📋</span>
                Study Management
              </h2>
            </div>
            <div className="p-6">
              <div className="mb-6">
                <label className="block text-sm font-bold text-gray-700 mb-2">Study Identifier</label>
                <input
                  type="text"
                  value={studyId}
                  onChange={(e) => setStudyId(e.target.value)}
                  className="input-field"
                  placeholder="Enter Study ID (e.g., STUDY-12345)"
                />
              </div>
              <div className="flex gap-3 mb-6">
                <button onClick={openStudy} className="btn-success flex items-center space-x-2 flex-1">
                  <span>📂</span>
                  <span>Open Study</span>
                </button>
                <button onClick={closeStudy} className="btn-danger flex items-center space-x-2 flex-1">
                  <span>📁</span>
                  <span>Close Study</span>
                </button>
              </div>
              <div className="terminal p-4 rounded-lg max-h-80 overflow-y-auto whitespace-pre-wrap text-sm">
                {responses.study || '🖥️  Study management responses will appear here...\n\nWaiting for user action...'}
              </div>
            </div>
          </div>

          {/* WebSocket Management Section */}
          <div className="card animate-fade-in">
            <div className="card-header">
              <h2 className="text-xl font-bold text-gray-800 flex items-center">
                <span className="text-2xl mr-3">🔌</span>
                WebSocket Management
              </h2>
            </div>
            <div className="p-6">
              <div className="mb-6">
                <label className="block text-sm font-bold text-gray-700 mb-2">Application Type</label>
                <select
                  value={appType}
                  onChange={(e) => setAppType(e.target.value as 'viewer' | 'dictation')}
                  className="input-field"
                >
                  <option value="viewer">📺 Viewer Application</option>
                  <option value="dictation">🎤 Dictation Application</option>
                </select>
              </div>
              <div className="flex flex-wrap gap-3 mb-6">
                <button onClick={registerWebSocket} className="btn-primary flex items-center space-x-2">
                  <span>🔗</span>
                  <span>Register</span>
                </button>
                <button onClick={getWebSocketStatus} className="btn-info flex items-center space-x-2">
                  <span>📊</span>
                  <span>Status</span>
                </button>
                <button onClick={getActiveConnections} className="btn-success flex items-center space-x-2">
                  <span>👥</span>
                  <span>Connections</span>
                </button>
              </div>
              <div className="terminal p-4 rounded-lg max-h-80 overflow-y-auto whitespace-pre-wrap text-sm">
                {responses.ws || '🖥️  WebSocket responses will appear here...\n\nWaiting for user action...'}
              </div>
            </div>
          </div>

          {/* Session State Section */}
          <div className="card animate-fade-in">
            <div className="card-header">
              <h2 className="text-xl font-bold text-gray-800 flex items-center">
                <span className="text-2xl mr-3">📊</span>
                Session State Monitor
              </h2>
            </div>
            <div className="p-6">
              <div className="flex gap-3 mb-6">
                <button onClick={getSessionState} className="btn-info flex items-center space-x-2 flex-1">
                  <span>📈</span>
                  <span>Get State</span>
                </button>
                <button onClick={logoutUser} className="btn-danger flex items-center space-x-2 flex-1">
                  <span>🔒</span>
                  <span>Clear Session</span>
                </button>
              </div>
              <div className="terminal p-4 rounded-lg max-h-80 overflow-y-auto whitespace-pre-wrap text-sm">
                {responses.session || '🖥️  Session state responses will appear here...\n\nWaiting for user action...'}
              </div>
            </div>
          </div>
        </div>

        {/* Health Check Section */}
        <div className="card mt-8 animate-fade-in">
          <div className="card-header">
            <h2 className="text-xl font-bold text-gray-800 flex items-center">
              <span className="text-2xl mr-3">❤️</span>
              System Health Monitor
            </h2>
            <p className="text-gray-600 mt-2">Check the health status of your API endpoints</p>
          </div>
          <div className="p-6">
            <button onClick={healthCheck} className="btn-info flex items-center space-x-2 mb-6">
              <span>🏥</span>
              <span>Run Health Check</span>
            </button>
            <div className="terminal p-4 rounded-lg max-h-80 overflow-y-auto whitespace-pre-wrap text-sm">
              {responses.health || '🖥️  Health check responses will appear here...\n\nClick "Run Health Check" to test system status...'}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center mt-12 pb-8">
          <div className="inline-flex items-center space-x-2 bg-white/10 backdrop-blur-sm rounded-full px-6 py-3 text-white">
            <span className="animate-pulse">🔐</span>
            <span className="font-medium">Keycloak Authentication Testing Suite</span>
            <span className="animate-pulse">🛠️</span>
          </div>
        </div>
      </div>
    </div>
  );
}