import java.net.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.logging.Logger;

public class webServer {
    public static void main(String[] args) throws IOException {
        // ========== (1) 建立连接 ==========
        // 创建ServerSocket，在8888端口监听，等待客户端连接
        ServerSocket ss = new ServerSocket(8888);
        System.out.println("Server started on port 8888");

        // 循环接受客户端连接，每个连接分配一个独立线程处理
        while (true) {
            Socket socket = ss.accept();
            Thread thread = new Thread(new RequestHandler(socket));
            thread.start();
        }
    }
}

class RequestHandler implements Runnable {
    private static final Logger logger = Logger.getLogger(RequestHandler.class.getName());
    private Socket clientSocket;

    public RequestHandler(Socket socket) {
        this.clientSocket = socket;
    }

    @Override
    public void run() {
        // try-with-resources 保证连接在处理完成后自动关闭（步骤4：关闭连接）
        try (Socket socket = this.clientSocket;
             InputStream inputStream = socket.getInputStream();
             OutputStream outputStream = socket.getOutputStream()) {

            // ========== (2) 接收并解析HTTP请求 ==========
            // 读取请求行，解析出：方法(GET/HEAD/POST)、请求URL、HTTP版本号
            String request = readLine(inputStream);
            if (request == null || request.isEmpty()) {
                return;
            }

            String[] params = request.split(" ");
            if (params.length < 3) {
                sendErrorResponse(outputStream, "HTTP/1.0", "400 Bad Request", "text/html");
                return;
            }

            String method = params[0];
            String url = params[1];
            String version = params[2];

            // 读取并记录请求头部信息，直到遇到空行表示头部结束
            String line = readLine(inputStream);
            while (line != null && !line.isEmpty()) {
                logger.info(line);
                line = readLine(inputStream);
            }

            // 安全检查：拒绝包含".."的路径，防止路径遍历攻击
            if (url.contains("..")) {
                sendErrorResponse(outputStream, version, "403 Forbidden", "text/html");
                return;
            }

            // ========== (3) 从服务器文件系统获取被请求的文件 ==========
            // 根据请求方法进行不同处理，映射URL到webroot目录下的文件
            String statusCode;
            String contentType;
            byte[] responseBody;
            long contentLength = 0;

            switch (method) {
                case "GET": {
                    // 默认首页处理
                    if (url.equals("/")) {
                        url = "/index.html";
                    }
                    // 规范化路径并验证仍在webroot目录内，防止路径遍历
                    Path filePath = Paths.get("webroot", url).normalize();
                    if (!filePath.startsWith(Paths.get("webroot").normalize())) {
                        statusCode = "403 Forbidden";
                        responseBody = "<h1>403 Forbidden</h1>".getBytes(StandardCharsets.UTF_8);
                        contentType = "text/html";
                        contentLength = responseBody.length;
                        break;
                    }
                    File file = filePath.toFile();

                    if (!file.exists() || file.isDirectory()) {
                        statusCode = "404 Not Found";
                        responseBody = "<h1>404 Not Found</h1>".getBytes(StandardCharsets.UTF_8);
                        contentType = "text/html";
                        contentLength = responseBody.length;
                    } else {
                        statusCode = "200 OK";
                        responseBody = Files.readAllBytes(file.toPath());
                        contentType = getContentType(file.getName());
                        contentLength = responseBody.length;
                    }
                    break;
                }

                // HEAD方法：与GET类似，但只返回响应头，不返回响应体
                case "HEAD": {
                    if (url.equals("/")) {
                        url = "/index.html";
                    }
                    Path filePath = Paths.get("webroot", url).normalize();
                    if (!filePath.startsWith(Paths.get("webroot").normalize())) {
                        statusCode = "403 Forbidden";
                        responseBody = new byte[0];
                        contentType = "text/html";
                        contentLength = 0;
                        break;
                    }
                    File file = filePath.toFile();

                    if (!file.exists() || file.isDirectory()) {
                        statusCode = "404 Not Found";
                        responseBody = new byte[0];
                        contentType = "text/html";
                        contentLength = 0;
                    } else {
                        statusCode = "200 OK";
                        // HEAD方法只获取文件大小，不读取文件内容
                        contentLength = file.length();
                        contentType = getContentType(file.getName());
                        responseBody = new byte[0];
                    }
                    break;
                }

                // POST方法：未实现，返回501
                case "POST": {
                    statusCode = "501 Not Implemented";
                    responseBody = "<h1>501 Not Implemented</h1>".getBytes(StandardCharsets.UTF_8);
                    contentType = "text/html";
                    contentLength = responseBody.length;
                    break;
                }

                // 其他未知方法：返回400
                default: {
                    statusCode = "400 Bad Request";
                    responseBody = "<h1>400 Bad Request</h1>".getBytes(StandardCharsets.UTF_8);
                    contentType = "text/html";
                    contentLength = responseBody.length;
                    break;
                }
            }

            // ========== (3) 发送响应信息（对应实验要求的步骤4、5）==========
            // 构造状态行：格式为 HTTP版本号 状态码 原因叙述 CRLF
            String statusLine = version + " " + statusCode + "\r\n";

            // 构造响应头：包含内容类型、内容长度、服务器信息、连接控制
            String headers = "Content-Type: " + contentType + "\r\n"
                           + "Content-Length: " + contentLength + "\r\n"
                           + "Server: SimpleJavaWebServer/1.0\r\n"
                           + "Connection: close\r\n";

            // 状态行 + 响应头 + 空行（CRLF）组成完整的响应头部
            String responseHeader = statusLine + headers + "\r\n";

            // 发送响应头部
            outputStream.write(responseHeader.getBytes(StandardCharsets.UTF_8));

            // 发送响应体（HEAD方法不发送body）
            if (!method.equals("HEAD") && responseBody.length > 0) {
                outputStream.write(responseBody);
            }

            outputStream.flush();

            logger.info("Response: " + statusCode + " " + url);

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    // 逐字节读取一行（以 \r\n 或 \n 结尾），避免 BufferedReader 缓存字节流的问题
    private String readLine(InputStream is) throws IOException {
        StringBuilder sb = new StringBuilder();
        int ch;
        while ((ch = is.read()) != -1) {
            if (ch == '\r') {
                int next = is.read();
                if (next != '\n' && next != -1) {
                    sb.append((char) ch);
                    sb.append((char) next);
                }
                break;
            } else if (ch == '\n') {
                break;
            }
            sb.append((char) ch);
        }
        if (ch == -1 && sb.length() == 0) {
            return null;
        }
        return sb.toString();
    }

    // 发送错误响应的辅助方法
    private void sendErrorResponse(OutputStream os, String version, String statusCode, String contentType) throws IOException {
        byte[] body = ("<h1>" + statusCode + "</h1>").getBytes(StandardCharsets.UTF_8);
        String response = version + " " + statusCode + "\r\n"
                        + "Content-Type: " + contentType + "\r\n"
                        + "Content-Length: " + body.length + "\r\n"
                        + "Server: SimpleJavaWebServer/1.0\r\n"
                        + "Connection: close\r\n"
                        + "\r\n";
        os.write(response.getBytes(StandardCharsets.UTF_8));
        os.write(body);
        os.flush();
    }

    // 辅助方法 - 根据文件扩展名获取 Content-Type
    private String getContentType(String fileName) {
        if (fileName.endsWith(".html") || fileName.endsWith(".htm"))
            return "text/html; charset=UTF-8";
        else if (fileName.endsWith(".txt"))
            return "text/plain; charset=UTF-8";
        else if (fileName.endsWith(".jpg") || fileName.endsWith(".jpeg"))
            return "image/jpeg";
        else if (fileName.endsWith(".png"))
            return "image/png";
        else if (fileName.endsWith(".gif"))
            return "image/gif";
        else if (fileName.endsWith(".css"))
            return "text/css";
        else if (fileName.endsWith(".js"))
            return "application/javascript";
        else
            return "application/octet-stream";
    }
}
