from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import requests

class Server:
    def address(self):
        raise NotImplementedError

    def is_alive(self):
        raise NotImplementedError

    def serve(self, handler, path, query):
        raise NotImplementedError

class SimpleServer(Server):
    def __init__(self, addr):
        self.addr = addr
        self.parsed_url = urlparse(addr)

    def address(self):
        return self.addr

    def is_alive(self):
        try:
            response = requests.head(self.addr, timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    def serve(self, handler, path, query):
        target_url = f"{self.addr}{path}?{query}" if query else f"{self.addr}{path}"
        try:
            # Forward the HTTP request to the target server
            response = requests.request(
                method=handler.command,
                url=target_url,
                headers={key: value for key, value in handler.headers.items()},
                data=handler.rfile.read(int(handler.headers.get('Content-Length', 0))) if 'Content-Length' in handler.headers else None,
                timeout=5
            )
            # Send back the response from the target server
            handler.send_response(response.status_code)
            for key, value in response.headers.items():
                handler.send_header(key, value)
            handler.end_headers()
            handler.wfile.write(response.content)
        except Exception as e:
            handler.send_error(502, f"Bad Gateway: {e}")

class LoadBalancer:
    def __init__(self, port, servers):
        self.port = port
        self.round_robin_count = 0
        self.servers = servers

    def get_next_available_server(self):
        # Round-robin logic to get the next available server
        server = self.servers[self.round_robin_count % len(self.servers)]
        while not server.is_alive():
            self.round_robin_count += 1
            server = self.servers[self.round_robin_count % len(self.servers)]

        self.round_robin_count += 1
        return server

    def serve_proxy(self, handler):
        # Proxy the request to the selected server
        target_server = self.get_next_available_server()
        print(f"Forwarding request to address {target_server.address()}")
        parsed_url = urlparse(handler.path)
        path = parsed_url.path
        query = parsed_url.query
        target_server.serve(handler, path, query)

class ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.load_balancer.serve_proxy(self)

    def do_POST(self):
        self.server.load_balancer.serve_proxy(self)

    def do_PUT(self):
        self.server.load_balancer.serve_proxy(self)

    def do_DELETE(self):
        self.server.load_balancer.serve_proxy(self)

class LoadBalancerServer(HTTPServer):
    def __init__(self, server_address, handler_class, load_balancer):
        super().__init__(server_address, handler_class)
        self.load_balancer = load_balancer

if __name__ == "__main__":
    servers = [
        SimpleServer("https://www.facebook.com"),
        SimpleServer("http://www.bing.com"),
        SimpleServer("http://www.duckduckgo.com"),
    ]
    lb = LoadBalancer(8000, servers)

    server = LoadBalancerServer(("localhost", lb.port), ProxyHandler, lb)
    print(f"Serving requests at 'localhost:{lb.port}'")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down the server.")
        server.server_close()
