# Web Server Programming Experiment

## Goal
```txt
(1) Process an HTTP request
(2) Receive and parse an HTTP request
(3) Retrieve the requested file from the server's file system
(4) Construct an HTTP response message containing the requested file
(5) Send the response message directly to the client
```

## Structure
```
lab1/
├── src/
│   └── webServer.java      # Web server source code
├── webroot/                 # Server root directory for static files
│   ├── index.html           # Default home page
│   ├── hello.txt            # Plain text test file
│   └── style.css            # CSS stylesheet
└── README.md
```

## How to Compile and Run

### Compile
```bash
cd lab1/src
javac webServer.java
```

### Run
```bash
# Run from lab1/ directory so webroot path resolves correctly
cd lab1
java -cp src webServer
```

Server will listen on port `8888`.

### Test
Open browser and visit:
- `http://localhost:8888/` — index.html (default page)
- `http://localhost:8888/hello.txt` — plain text file
- `http://localhost:8888/style.css` — CSS file
- `http://localhost:8888/notfound.html` — 404 test

Or use command line:
```bash
# GET request
curl http://localhost:8888/

# HEAD request (only headers, no body)
curl -I http://localhost:8888/

# Request a non-existent file (404)
curl http://localhost:8888/notexist.html
```

## Implementation Details

### HTTP Methods Supported
| Method | Description |
|--------|-------------|
| GET    | Retrieve the requested resource and return it with response body |
| HEAD   | Same as GET but only returns headers, no response body |
| POST   | Returns 501 Not Implemented |

### Status Codes
| Code | Meaning |
|------|---------|
| 200  | OK — File found and returned successfully |
| 400  | Bad Request — Unrecognized HTTP method |
| 404  | Not Found — Requested file does not exist |
| 501  | Not Implemented — POST method not supported |

### Key Classes
- **`webServer`**: Main class, creates `ServerSocket` on port 8888, accepts connections and spawns a new thread for each client.
- **`RequestHandler`**: Implements `Runnable`, handles a single HTTP request including parsing, file retrieval, response construction, and sending.
