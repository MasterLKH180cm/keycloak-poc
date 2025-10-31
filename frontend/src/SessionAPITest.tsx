import React, { useState, useEffect } from "react";
import { Button } from "./components/ui/button";
import { Card, CardContent } from "./components/ui/card";


export default function SessionAPITest() {
  // State for inputs
  const [studyId, setStudyId] = useState("STUDY_123");
  const [sessionId, setSessionId] = useState("");
  const [eventId, setEventId] = useState("");
  const [response, setResponse] = useState("");
  
  // Authentication state
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userInfo, setUserInfo] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [accessToken, setAccessToken] = useState("");

  // Additional test data
  const [testData, setTestData] = useState({
    patientId: "SSE_Leia, Princess",
    patientDob: "1977-05-25",
    accessionNumber: "ACC123456",
    currentStudyName: "Chest CT with Contrast",
    source: "viewer",
    target: ["dictation", "worklist"]
  });

  // API base URL - adjust based on your backend configuration
  const API_BASE_URL = "http://localhost:8000";

  // Real API call function
  const makeAPICall = async (endpoint, method = "GET", body = null) => {
    try {
      setResponse("🔄 Making API call...");
      
      const options = {
        method,
        headers: { 
          "Content-Type": "application/json"
        },
      };

      // Add authorization header if we have a token and it's not a health check
      if (accessToken && !endpoint.includes("/health")) {
        options.headers["Authorization"] = `Bearer ${accessToken}`;
      }

      if (body && method !== "GET") {
        options.body = JSON.stringify(body);
      }

      const url = `${API_BASE_URL}${endpoint}`;
      console.log(`Making ${method} request to ${url}`);

      const response = await fetch(url, options);
      
      if (!response.ok) {
        const errorText = await response.text();
        let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
        
        try {
          const errorJson = JSON.parse(errorText);
          errorMessage = errorJson.detail || errorJson.message || errorMessage;
        } catch {
          errorMessage = errorText || errorMessage;
        }
        
        throw new Error(errorMessage);
      }

      const responseData = await response.json();
      setResponse(JSON.stringify(responseData, null, 2));
      
      return responseData;
    } catch (err) {
      console.error("API call failed:", err);
      setResponse(`❌ Error: ${err.message}`);
      throw err;
    }
  };

  // Simple token-based authentication for testing
  const handleLogin = async () => {
    try {
      setError("");
      setIsLoading(true);
      setResponse("🔄 Attempting to login...");
      
      // For testing, we'll use a simple token input
      const token = prompt("Enter your JWT token (get it from Keycloak login):");
      
      if (!token) {
        throw new Error("Token is required");
      }
      
      // Validate token by making a call to get session state
      const options = {
        method: "GET",
        headers: { 
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        }
      };

      const response = await fetch(`${API_BASE_URL}/session/api/get_session_state`, options);
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Authentication failed: ${errorText}`);
      }

      const sessionData = await response.json();
      
      setAccessToken(token);
      setIsAuthenticated(true);
      setUserInfo(sessionData.user_info || { preferred_username: "authenticated_user" });
      setResponse("✅ Authentication successful!\n" + JSON.stringify(sessionData, null, 2));
      
    } catch (error) {
      setError(`❌ Login error: ${error.message}`);
      setResponse(`❌ Login error: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      setResponse("🔄 Logging out...");
      
      // Call logout endpoint if authenticated
      if (isAuthenticated && accessToken) {
        try {
          await makeAPICall("/session/api/logout", "POST");
        } catch (error) {
          console.warn("Backend logout failed:", error);
        }
      }
      
      // Clear local state
      setIsAuthenticated(false);
      setUserInfo(null);
      setAccessToken("");
      setResponse("✅ Logged out successfully");
    } catch (error) {
      setResponse(`❌ Logout error: ${error.message}`);
    }
  };

  const handleStudyOpened = async () => {
    const body = {
      study_id: studyId,
      patient_id: testData.patientId,
      patient_dob: testData.patientDob,
      accession_number: testData.accessionNumber,
      current_study_name: testData.currentStudyName,
      source: testData.source,
      target: testData.target
    };

    await makeAPICall("/session/api/study_opened", "POST", body);
  };

  const handleStudyClosed = async () => {
    const body = {
      study_id: studyId,
      source: testData.source,
      target: testData.target
    };

    await makeAPICall("/session/api/study_closed", "POST", body);
  };

  const handleWebSocketTest = async (appType) => {
    const body = {
      app_id: appType,
      client_info: {
        browser: navigator.userAgent,
        timestamp: new Date().toISOString()
      }
    };

    await makeAPICall(`/session/api/open_websocket/${appType}`, "POST", body);
  };

  const checkWebSocketStatus = async (appType) => {
    await makeAPICall(`/session/api/websocket_status/${appType}`, "GET");
  };

  // Initialize component
  useEffect(() => {
    setResponse(`📱 Session API Test Component Loaded\n\nAPI Base URL: ${API_BASE_URL}\n\nLogin with your JWT token to start testing APIs.`);
  }, []);

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
          <strong>Error:</strong> {error}
          <button
            onClick={() => setError("")}
            className="ml-4 bg-red-500 text-white px-2 py-1 rounded text-sm"
          >
            Clear
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 bg-gray-50 min-h-screen">
      {/* Header */}
      <div className="text-center py-4">
        <h1 className="text-3xl font-bold text-gray-900">🧪 Session API Test</h1>
        <p className="text-gray-600 mt-2">Test session management and authentication APIs</p>
        <p className="text-sm text-gray-500 mt-1">Backend: {API_BASE_URL}</p>
      </div>

      {/* Authentication Status */}
      <Card className="shadow-lg">
        <CardContent className="p-6">
          <h2 className="text-xl font-semibold mb-4">🔐 Authentication Status</h2>
          
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                isAuthenticated 
                  ? "bg-green-100 text-green-800" 
                  : "bg-red-100 text-red-800"
              }`}>
                {isAuthenticated ? "✅ Authenticated" : "❌ Not Authenticated"}
              </span>
              
              {userInfo && (
                <span className="text-sm text-gray-600">
                  User: {userInfo.preferred_username || userInfo.email}
                </span>
              )}
            </div>

            <div className="flex gap-3">
              {!isAuthenticated ? (
                <Button 
                  onClick={handleLogin} 
                  className="bg-blue-600 hover:bg-blue-700"
                  disabled={isLoading}
                >
                  {isLoading ? "🔄 Logging in..." : "🔐 Login with Token"}
                </Button>
              ) : (
                <Button 
                  onClick={handleLogout} 
                  variant="outline" 
                  className="border-red-300 text-red-600 hover:bg-red-50"
                >
                  🚪 Logout
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Session Management API Test */}
      <Card className="shadow-lg">
        <CardContent className="space-y-4 p-6">
          <h2 className="text-xl font-semibold mb-4">📋 Session Management API</h2>

          {/* Test Data Configuration */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6 p-4 bg-gray-50 rounded-lg">
            <div>
              <label className="block text-sm font-medium mb-1">Study ID</label>
              <input
                type="text"
                value={studyId}
                onChange={(e) => setStudyId(e.target.value)}
                placeholder="Enter study ID"
                className="w-full rounded-lg border px-3 py-2 focus:outline-none focus:ring focus:ring-blue-300"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Patient ID</label>
              <input
                type="text"
                value={testData.patientId}
                onChange={(e) => setTestData({...testData, patientId: e.target.value})}
                className="w-full rounded-lg border px-3 py-2 focus:outline-none focus:ring focus:ring-blue-300"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Source App</label>
              <select
                value={testData.source}
                onChange={(e) => setTestData({...testData, source: e.target.value})}
                className="w-full rounded-lg border px-3 py-2 focus:outline-none focus:ring focus:ring-blue-300"
              >
                <option value="viewer">Viewer</option>
                <option value="dictation">Dictation</option>
                <option value="worklist">Worklist</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Target Apps</label>
              <div className="flex gap-2">
                {["viewer", "dictation", "worklist"].map(app => (
                  <label key={app} className="flex items-center">
                    <input
                      type="checkbox"
                      checked={testData.target.includes(app)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setTestData({...testData, target: [...testData.target, app]});
                        } else {
                          setTestData({...testData, target: testData.target.filter(t => t !== app)});
                        }
                      }}
                      className="mr-1"
                    />
                    {app}
                  </label>
                ))}
              </div>
            </div>
          </div>

          {/* Session Event APIs */}
          <div className="space-y-3">
            <h3 className="text-lg font-medium">📝 Session Events</h3>
            <div className="flex flex-wrap gap-3">
              <Button 
                onClick={handleStudyOpened}
                disabled={!isAuthenticated}
                className="bg-green-600 hover:bg-green-700"
              >
                📖 Open Study (New API)
              </Button>
              <Button 
                onClick={handleStudyClosed}
                disabled={!isAuthenticated}
                className="bg-orange-600 hover:bg-orange-700"
              >
                📕 Close Study (New API)
              </Button>
              <Button 
                onClick={() => makeAPICall("/session/api/get_session_state", "GET")}
                disabled={!isAuthenticated}
                className="bg-blue-600 hover:bg-blue-700"
              >
                📊 Get Session State
              </Button>
            </div>
          </div>

          {/* Legacy Study APIs */}
          <div className="space-y-3">
            <h3 className="text-lg font-medium">🔄 Legacy Study APIs</h3>
            <div className="flex flex-wrap gap-3">
              <Button 
                onClick={() => makeAPICall(`/session/api/viewer/study_opened/${studyId}`, "POST")}
                disabled={!isAuthenticated}
                variant="outline"
              >
                📖 Legacy Open Study
              </Button>
              <Button 
                onClick={() => makeAPICall(`/session/api/viewer/study_closed/${studyId}`, "POST")}
                disabled={!isAuthenticated}
                variant="outline"
              >
                📕 Legacy Close Study
              </Button>
            </div>
          </div>

          {/* WebSocket APIs */}
          <div className="space-y-3">
            <h3 className="text-lg font-medium">🔌 WebSocket Management</h3>
            <div className="flex flex-wrap gap-3">
              <Button 
                onClick={() => handleWebSocketTest("viewer")}
                disabled={!isAuthenticated}
                className="bg-purple-600 hover:bg-purple-700"
              >
                🔌 Open WebSocket (Viewer)
              </Button>
              <Button 
                onClick={() => handleWebSocketTest("dictation")}
                disabled={!isAuthenticated}
                className="bg-purple-600 hover:bg-purple-700"
              >
                🔌 Open WebSocket (Dictation)
              </Button>
              <Button 
                onClick={() => checkWebSocketStatus("viewer")}
                disabled={!isAuthenticated}
                variant="outline"
              >
                📊 Check Status (Viewer)
              </Button>
              <Button 
                onClick={() => makeAPICall("/session/api/active_connections", "GET")}
                disabled={!isAuthenticated}
                variant="outline"
              >
                📡 Active Connections
              </Button>
            </div>
          </div>

          {/* Health Check */}
          <div className="space-y-3">
            <h3 className="text-lg font-medium">❤️ Health Checks</h3>
            <div className="flex flex-wrap gap-3">
              <Button 
                onClick={() => makeAPICall("/session/api/health", "GET")}
                className="bg-gray-600 hover:bg-gray-700"
              >
                ❤️ Session Health
              </Button>
              <Button 
                onClick={() => makeAPICall("/session/api/viewer/health", "GET")}
                className="bg-gray-600 hover:bg-gray-700"
              >
                ❤️ Viewer Health
              </Button>
            </div>
          </div>

          {/* Response Display */}
          <div className="mt-6">
            <div className="flex justify-between items-center mb-2">
              <label className="block text-sm font-medium">API Response</label>
              <Button 
                onClick={() => setResponse("")}
                variant="outline"
                size="sm"
              >
                🗑️ Clear
              </Button>
            </div>
            <textarea
              readOnly
              value={response}
              placeholder="API response will appear here..."
              className="w-full h-64 rounded-lg border px-3 py-2 font-mono text-sm focus:outline-none bg-white"
            />
          </div>
        </CardContent>
      </Card>

      {/* Debug Information */}
      {isAuthenticated && (
        <Card className="shadow-lg">
          <CardContent className="p-6">
            <h3 className="text-lg font-semibold mb-4">🔍 Debug Information</h3>
            <div className="space-y-2 text-sm">
              <div>
                <strong>Authentication Status:</strong> 
                <span className="ml-2 px-2 py-1 rounded text-xs bg-green-100 text-green-800">
                  ✅ Token Valid
                </span>
              </div>
              <div><strong>User ID:</strong> {userInfo?.sub}</div>
              <div><strong>Username:</strong> {userInfo?.preferred_username}</div>
              <div><strong>Email:</strong> {userInfo?.email}</div>
              <div><strong>Roles:</strong> {JSON.stringify(userInfo?.roles || [])}</div>
              <div><strong>Token Preview:</strong> {accessToken ? `${accessToken.substring(0, 20)}...` : "No token"}</div>
              <div><strong>API Base URL:</strong> {API_BASE_URL}</div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Footer */}
      <div className="text-center py-4 text-gray-500">
        <p>🔗 Connected to real backend API</p>
      </div>
    </div>
  );
}
