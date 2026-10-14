#include "reporter.h"

#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>

#include <atomic>
#include <condition_variable>
#include <deque>
#include <mutex>
#include <thread>

#include "hook_log.h"

namespace gg {
namespace {
constexpr size_t kMaxQueued = 64;

std::mutex g_mutex;
std::condition_variable g_wake;
std::deque<std::string> g_queue;
std::atomic<bool> g_running{false};
std::thread g_worker;

void WorkerMain() {
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) {
        Log("reporter: WSAStartup failed");
        return;
    }
    SOCKET sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock == INVALID_SOCKET) {
        Log("reporter: socket() failed");
        WSACleanup();
        return;
    }
    sockaddr_in target{};
    target.sin_family = AF_INET;
    target.sin_port = htons(kReporterPort);
    target.sin_addr.s_addr = htonl(INADDR_LOOPBACK);

    while (g_running.load()) {
        std::string line;
        {
            std::unique_lock<std::mutex> lock(g_mutex);
            g_wake.wait(lock, [] { return !g_queue.empty() || !g_running.load(); });
            if (g_queue.empty()) {
                continue;
            }
            line = std::move(g_queue.front());
            g_queue.pop_front();
        }
        // Fire and forget: nobody listening is a normal state.
        sendto(sock, line.data(), static_cast<int>(line.size()), 0,
               reinterpret_cast<const sockaddr*>(&target), sizeof(target));
    }
    closesocket(sock);
    WSACleanup();
}
}  // namespace

void Report(std::string line) {
    {
        std::lock_guard<std::mutex> lock(g_mutex);
        if (g_queue.size() >= kMaxQueued) {
            return;
        }
        g_queue.push_back(std::move(line));
    }
    g_wake.notify_one();
}

void StartReporter() {
    if (g_running.exchange(true)) {
        return;
    }
    g_worker = std::thread(WorkerMain);
}

void StopReporter() {
    if (!g_running.exchange(false)) {
        return;
    }
    g_wake.notify_all();
    if (g_worker.joinable()) {
        g_worker.join();
    }
}
}  // namespace gg
