import React, { useState } from "react";
import { Button } from "./components/ui/button";
import { Card, CardContent } from "./components/ui/card";

export default function SessionManagementAPI() {
  const [studyId, setStudyId] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [eventId, setEventId] = useState("");
  const [response, setResponse] = useState("");

  const handleAPICall = async (endpoint: string, method: string = "POST") => {
    try {
      const res = await fetch(endpoint, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ studyId, sessionId, eventId }),
      });
      const data = await res.json();
      setResponse(JSON.stringify(data, null, 2));
    } catch (err) {
      setResponse(`Error: ${err}`);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <Card className="shadow-lg">
        <CardContent className="space-y-4 p-6">
          <h2 className="text-xl font-semibold mb-4">📋 Session Management API</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Study ID */}
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

            {/* Session ID */}
            <div>
              <label className="block text-sm font-medium mb-1">Session ID</label>
              <input
                type="text"
                value={sessionId}
                onChange={(e) => setSessionId(e.target.value)}
                placeholder="Enter session ID"
                className="w-full rounded-lg border px-3 py-2 focus:outline-none focus:ring focus:ring-blue-300"
              />
            </div>

            {/* Event ID */}
            <div>
              <label className="block text-sm font-medium mb-1">Event UUID</label>
              <input
                type="text"
                value={eventId}
                onChange={(e) => setEventId(e.target.value)}
                placeholder="Enter event UUID"
                className="w-full rounded-lg border px-3 py-2 focus:outline-none focus:ring focus:ring-blue-300"
              />
            </div>
          </div>

          {/* API Buttons */}
          <div className="flex flex-wrap gap-3 mt-6">
            <Button onClick={() => handleAPICall("/session/api/viewer/study_opened")}>
              Open Study
            </Button>
            <Button onClick={() => handleAPICall("/session/api/viewer/study_closed")}>
              Close Study
            </Button>
            <Button onClick={() => handleAPICall("/session/api/viewer/health", "GET")}>
              Health Check
            </Button>
            <Button onClick={() => handleAPICall("/session/api/viewer/socket_test")}>
              WebSocket Test
            </Button>
            <Button onClick={() => handleAPICall("/session/api/viewer/reset", "POST")}>
              Reset Session
            </Button>
          </div>

          {/* Response Viewer */}
          <div className="mt-6">
            <label className="block text-sm font-medium mb-1">Response</label>
            <textarea
              readOnly
              value={response}
              placeholder="API response will appear here..."
              className="w-full h-48 rounded-lg border px-3 py-2 font-mono text-sm focus:outline-none bg-gray-50"
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
