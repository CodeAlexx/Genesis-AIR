#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <mmsystem.h>
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <string>
#include <vector>

// One device owned by the window thread. Completed buffers are reclaimed before every call.
// The AIR layer supplies bounded, already mixed PCM chunks; the device clock drives the playhead.
namespace {
struct Block { std::vector<char> data; WAVEHDR header{}; std::uint64_t start = 0; };
HWAVEOUT device = nullptr;
std::vector<std::unique_ptr<Block>> blocks;
std::string reply;
std::uint64_t queued_samples = 0;
struct Position {
  UINT type = 0;
  std::uint32_t previous = 0;
  std::uint64_t ticks = 0, samples = 0;
  void reset() { *this = {}; }
  std::uint64_t read(UINT unit, std::uint32_t raw) {
    constexpr std::uint64_t period = std::uint64_t(1) << 32;
    if (type != unit) {
      // Reconstruct the nearest epoch when a driver changes its reported unit.
      // Unwrap the native counter BEFORE converting bytes or milliseconds.
      auto expected = unit == TIME_BYTES ? samples * 4 : unit == TIME_MS ? samples / 48 : samples;
      ticks = (expected & ~(period - 1)) | raw;
      if (ticks < expected && expected - ticks > period / 2) ticks += period;
      else if (ticks > expected && ticks - expected > period / 2 && ticks >= period) ticks -= period;
      previous = raw;
      type = unit;
    } else {
      // A small unsigned delta spans rollover. A negative/jittering driver
      // observation has a large delta; hold the last position until it catches up.
      const std::uint32_t delta = raw - previous;
      if (delta <= INT32_MAX) { ticks += delta; previous = raw; }
    }
    auto converted = unit == TIME_BYTES ? ticks / 4 : unit == TIME_MS ? ticks * 48 : ticks;
    samples = std::max(samples, converted);
    return samples;
  }
} cursor;
void collect() {
  for (auto it = blocks.begin(); it != blocks.end();) {
    if ((*it)->header.dwFlags & WHDR_DONE) {
      waveOutUnprepareHeader(device, &(*it)->header, sizeof(WAVEHDR));
      it = blocks.erase(it);
    } else ++it;
  }
}
void stop() {
  if (device) {
    waveOutReset(device);
    for (auto &block : blocks) waveOutUnprepareHeader(device, &block->header, sizeof(WAVEHDR));
    blocks.clear(); waveOutClose(device); device = nullptr;
  }
  cursor.reset(); queued_samples = 0;
}
MMRESULT position(std::uint64_t &samples) {
  MMTIME value{}; value.wType = TIME_SAMPLES;
  MMRESULT status = waveOutGetPosition(device, &value, sizeof(value));
  if (status != MMSYSERR_NOERROR) return status;
  std::uint32_t raw;
  if (value.wType == TIME_SAMPLES) raw = value.u.sample;
  else if (value.wType == TIME_BYTES) raw = value.u.cb;
  else if (value.wType == TIME_MS) raw = value.u.ms;
  else return MMSYSERR_NOTSUPPORTED;
  samples = cursor.read(value.wType, raw);
  return MMSYSERR_NOERROR;
}
const char *failure(const char *code, unsigned detail) {
  reply = std::string("[GA_AUDIO_") + code + "] Windows audio error " + std::to_string(detail);
  return reply.c_str();
}
std::wstring wide(const char *value) {
  int size = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value, -1, nullptr, 0);
  if (size < 1) return {};
  std::wstring result(size, L'\0');
  MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value, -1, result.data(), size);
  result.resize(size - 1); return result;
}
bool wave(const char *filename, std::vector<char> &data) {
  auto path = wide(filename);
  HANDLE file = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, 0, nullptr);
  if (file == INVALID_HANDLE_VALUE) return false;
  LARGE_INTEGER size{};
  if (!GetFileSizeEx(file, &size) || size.QuadPart < 44 || size.QuadPart > 16 * 1024 * 1024) {
    CloseHandle(file); return false;
  }
  std::vector<char> raw(static_cast<size_t>(size.QuadPart)); DWORD got;
  bool read = ReadFile(file, raw.data(), static_cast<DWORD>(raw.size()), &got, nullptr) && got == raw.size();
  CloseHandle(file);
  if (!read || memcmp(raw.data(), "RIFF", 4) || memcmp(raw.data() + 8, "WAVE", 4)) return false;
  bool format = false;
  for (size_t at = 12; at + 8 <= raw.size();) {
    uint32_t length; memcpy(&length, raw.data() + at + 4, 4);
    if (length > raw.size() - at - 8) return false;
    if (!memcmp(raw.data() + at, "fmt ", 4)) {
      if (length < 16) return false;
      WAVEFORMATEX fmt{}; memcpy(&fmt, raw.data() + at + 8, 16);
      format = fmt.wFormatTag == WAVE_FORMAT_PCM && fmt.nChannels == 2 &&
        fmt.nSamplesPerSec == 48000 && fmt.wBitsPerSample == 16 && fmt.nBlockAlign == 4;
    } else if (!memcmp(raw.data() + at, "data", 4) && format && length && length % 4 == 0) {
      data.assign(raw.begin() + at + 8, raw.begin() + at + 8 + length); return true;
    }
    at += 8 + length + (length & 1);
  }
  return false;
}
}
extern "C" __declspec(dllexport) const char *air_genesis_audio(const char *operation, const char *filename) {
  if (!operation || !filename) return failure("ARGUMENT", 0);
  if (!strcmp(operation, "stop")) { stop(); return "ok"; }
  if (!strcmp(operation, "start")) {
    stop(); WAVEFORMATEX format{};
    format.wFormatTag = WAVE_FORMAT_PCM; format.nChannels = 2; format.nSamplesPerSec = 48000;
    format.wBitsPerSample = 16; format.nBlockAlign = 4; format.nAvgBytesPerSec = 192000;
    MMRESULT status = waveOutOpen(&device, WAVE_MAPPER, &format, 0, 0, CALLBACK_NULL);
    if (status != MMSYSERR_NOERROR) { device = nullptr; return failure("DEVICE", status); }
    return "ok";
  }
  if (!device) return failure("CLOSED", 0);
  collect();
  if (!strcmp(operation, "clock") || !strcmp(operation, "levels")) {
    std::uint64_t samples = 0;
    MMRESULT status = position(samples);
    if (status != MMSYSERR_NOERROR) return failure("CLOCK", status);
    if (!strcmp(operation, "clock")) {
      reply = std::to_string(samples) + " " + std::to_string(blocks.size());
    } else {
      // Meter the next 50 ms of the PCM at the device cursor, after the complete mix.
      int left = 0, right = 0;
      for (const auto &block : blocks) {
        auto begin = std::max(samples, block->start);
        auto end = std::min(samples + 2400, block->start + block->data.size() / 4);
        for (auto at = begin; at < end; ++at) {
          std::int16_t pair[2];
          memcpy(pair, block->data.data() + (at - block->start) * 4, sizeof(pair));
          left = std::max(left, std::abs(int(pair[0])));
          right = std::max(right, std::abs(int(pair[1])));
        }
      }
      reply = std::to_string(left / 32768.0) + " " + std::to_string(right / 32768.0);
    }
    return reply.c_str();
  }
  if (!strcmp(operation, "queue")) {
    if (blocks.size() >= 4) return failure("QUEUE_FULL", 0);
    auto block = std::make_unique<Block>();
    if (!wave(filename, block->data)) return failure("WAVE_FORMAT", 0);
    block->start = queued_samples;
    block->header.lpData = block->data.data();
    block->header.dwBufferLength = static_cast<DWORD>(block->data.size());
    MMRESULT status = waveOutPrepareHeader(device, &block->header, sizeof(WAVEHDR));
    if (status != MMSYSERR_NOERROR) return failure("PREPARE", status);
    status = waveOutWrite(device, &block->header, sizeof(WAVEHDR));
    if (status != MMSYSERR_NOERROR) {
      waveOutUnprepareHeader(device, &block->header, sizeof(WAVEHDR)); return failure("WRITE", status);
    }
    queued_samples += block->data.size() / 4;
    blocks.push_back(std::move(block)); return "ok";
  }
  return failure("OPERATION", 0);
}
