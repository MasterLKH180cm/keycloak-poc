# Hospital Authentication System - Frontend

A modern React frontend for testing and demonstrating the Hospital Authentication System with Keycloak integration.

## Features

- 🎨 Modern UI with Tailwind CSS
- 🔐 JWT token-based authentication
- 🧪 Comprehensive API testing interface
- 📊 Real-time session state visualization
- 🔌 WebSocket connection management
- 📱 Responsive design
- ⚡ Fast development with Vite HMR

## Tech Stack

- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Utility-first CSS framework
- **shadcn/ui** - UI component library

## Prerequisites

- Node.js 18+ or Bun
- Backend API running on `http://localhost:8000`

## Quick Start

### 1. Install dependencies

```bash
npm install
# or
bun install
```

### 2. Configure environment

Create a `.env` file (optional, defaults to localhost):

```bash
VITE_API_BASE_URL=http://localhost:8000
```

### 3. Run development server

```bash
npm run dev
# or
bun run dev
```

The application will be available at [http://localhost:3000](http://localhost:3000)

## Available Scripts

- `npm run dev` - Start development server on port 3000
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

## Project Structure

```
frontend/
├── public/              # Static assets
├── src/
│   ├── components/      # React components
│   │   └── ui/         # shadcn/ui components
│   ├── SessionAPITest.tsx  # Main testing component
│   ├── App.tsx         # App entry point
│   ├── App.css         # Global styles
│   └── main.tsx        # React DOM entry
├── index.html          # HTML template
├── vite.config.ts      # Vite configuration
├── tailwind.config.js  # Tailwind configuration
└── tsconfig.json       # TypeScript configuration
```

## Features Overview

### Authentication Testing
- Manual JWT token input for testing
- Token validation against backend
- User information display
- Logout functionality

### Session Management
- Study opened/closed events
- New event-based API testing
- Legacy API compatibility testing
- Session state retrieval
- Real-time event tracking

### WebSocket Testing
- Connection registration for different apps (Viewer, Dictation, Worklist)
- Connection status checks
- Active connections monitoring
- Multi-application support

### API Testing Interface
- Test data configuration
- Source/target app selection
- Real-time response display
- Error handling and logging
- Health check endpoints

## Development

### Using Vite

Vite provides instant hot module replacement (HMR) for a fast development experience:

```bash
npm run dev
```

### Building for Production

```bash
npm run build
```

The built files will be in the `dist/` directory.

### Preview Production Build

```bash
npm run preview
```

## Configuration

### Vite Configuration

The project uses Vite with the following plugins:
- `@vitejs/plugin-react` - React Fast Refresh
- `@tailwindcss/vite` - Tailwind CSS integration

Port is configured to 3000 in `vite.config.ts`.

### Tailwind CSS

Tailwind is configured with custom animations and utilities in `App.css`:
- Fade-in animations
- Slide-up animations
- Custom scrollbar styling
- Focus styles for accessibility

### Path Aliases

The project uses `@/` as an alias for the `src/` directory:

```typescript
import { Button } from "@/components/ui/button"
```

## API Integration

The frontend connects to the backend API at `http://localhost:8000` by default.

### Supported Endpoints

#### New Session Management
- `POST /session/api/study_opened` - Open study with full context
- `POST /session/api/study_closed` - Close study
- `GET /session/api/get_session_state` - Get session state

#### Legacy APIs
- `POST /session/api/viewer/study_opened/{study_id}`
- `POST /session/api/viewer/study_closed/{study_id}`

#### WebSocket Management
- `POST /session/api/open_websocket/{app_type}`
- `GET /session/api/websocket_status/{app_type}`
- `GET /session/api/active_connections`

#### Health Checks
- `GET /session/api/health`
- `GET /session/api/viewer/health`

## Testing Workflow

1. **Login**: Enter your JWT token from Keycloak login
2. **Configure Test Data**: Set study ID, patient info, source/target apps
3. **Test Session Events**: Open/close studies using new or legacy APIs
4. **Monitor WebSockets**: Register connections and check status
5. **View Responses**: All API responses displayed in real-time
6. **Check Debug Info**: View user info and authentication details

## Troubleshooting

### CORS Issues
- Ensure backend CORS is configured for `http://localhost:3000`
- Check backend logs for CORS errors

### API Connection Failed
- Verify backend is running on `http://localhost:8000`
- Check backend health endpoint: `http://localhost:8000/health`

### Authentication Failed
- Ensure you're using a valid JWT token from Keycloak
- Check token hasn't expired
- Verify token format (should start with `eyJ`)

### Build Errors
- Clear node_modules: `rm -rf node_modules && npm install`
- Clear Vite cache: `rm -rf node_modules/.vite`

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

## License

Proprietary - Hospital Authentication System
