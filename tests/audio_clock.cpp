// Exercise the actual native ABI with controlled driver positions, without a device.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <mmsystem.h>
#include <cstdio>
#include <cstdlib>

namespace {
UINT reported_type = TIME_SAMPLES;
DWORD reported_value = 0;
MMRESULT reported_status = MMSYSERR_NOERROR;
unsigned checks = 0;
MMRESULT WINAPI driver_position(HWAVEOUT, LPMMTIME value, UINT size) {
  if (size != sizeof(MMTIME) || value->wType != TIME_SAMPLES) std::abort();
  value->wType = reported_type;
  value->u.sample = reported_value;
  return reported_status;
}
}
#define waveOutGetPosition driver_position
#include "../windows/native_audio.cpp"
#undef waveOutGetPosition

namespace {
void expect(bool condition, const char *label) {
  ++checks;
  if (!condition) { std::fprintf(stderr, "[GA_TEST_AUDIO_CLOCK] %s\n", label); std::exit(1); }
}
void clock_at(UINT unit, DWORD raw, std::uint64_t expected, const char *label) {
  reported_type = unit; reported_value = raw; reported_status = MMSYSERR_NOERROR;
  const char *answer = air_genesis_audio("clock", "");
  unsigned long long samples = 0, pending = 0;
  expect(std::sscanf(answer, "%llu %llu", &samples, &pending) == 2 &&
         samples == expected && pending == blocks.size(), label);
}
void restart() { cursor.reset(); blocks.clear(); queued_samples = 0; }
}
int main() {
  device = reinterpret_cast<HWAVEOUT>(1); // only the controlled position API is called
  for (UINT unit : {TIME_SAMPLES, TIME_BYTES, TIME_MS}) {
    restart();
    const std::uint64_t scale = unit == TIME_MS ? 48 : 1;
    const std::uint64_t divisor = unit == TIME_BYTES ? 4 : 1;
    clock_at(unit, 0, 0, "fresh clock");
    clock_at(unit, 100, 100 * scale / divisor, "native unit conversion");
    clock_at(unit, 99, 100 * scale / divisor, "one-tick backward observation holds");
    clock_at(unit, 0, 100 * scale / divisor, "larger backward observation holds");
    clock_at(unit, 101, 101 * scale / divisor, "clock resumes after jitter");
    restart();
    clock_at(unit, 0xfffffffc, std::uint64_t(0xfffffffc) * scale / divisor, "counter near rollover");
    clock_at(unit, 3, ((std::uint64_t(1) << 32) + 3) * scale / divisor, "native 32-bit rollover");
    clock_at(unit, 2, ((std::uint64_t(1) << 32) + 3) * scale / divisor, "post-rollover jitter holds");
    clock_at(unit, 8, ((std::uint64_t(1) << 32) + 8) * scale / divisor, "post-rollover forward position");
    clock_at(unit, 0x70000000, 6174015488 * scale / divisor, "advance within long counter epoch");
    clock_at(unit, 0xe0000000, 8053063680 * scale / divisor, "advance before second rollover");
    clock_at(unit, 0x50000000, 9932111872 * scale / divisor, "second counter rollover");
    clock_at(unit, 0xc0000000, 11811160064 * scale / divisor, "advance after second rollover");
    clock_at(unit, 0x30000000, 13690208256 * scale / divisor, "third counter rollover");
  }
  // Changes of position units retain the same media time, including byte counters
  // that have wrapped four times while a sample counter has wrapped once.
  restart();
  clock_at(TIME_SAMPLES, 0xfffffffc, 4294967292, "long sample position");
  clock_at(TIME_SAMPLES, 8, 4294967304, "wrapped sample position");
  clock_at(TIME_BYTES, 36, 4294967305, "switch to wrapped byte units");
  clock_at(TIME_MS, 89478485, 4294967305, "coarse milliseconds retain last sample");
  clock_at(TIME_MS, 89478486, 4294967328, "millisecond counter advances");
  clock_at(TIME_BYTES, 128, 4294967328, "switch back to byte units");
  clock_at(TIME_SAMPLES, 33, 4294967329, "switch back to sample units");
  reported_type = TIME_SMPTE;
  expect(std::strstr(air_genesis_audio("clock", ""), "[GA_AUDIO_CLOCK]") != nullptr,
         "unsupported clock type has a code");
  clock_at(TIME_SAMPLES, 34, 4294967330, "unsupported type preserves valid state");
  reported_status = MMSYSERR_ERROR;
  expect(std::strstr(air_genesis_audio("clock", ""), "[GA_AUDIO_CLOCK]") != nullptr,
         "driver failure has a code");
  clock_at(TIME_SAMPLES, 35, 4294967331, "driver failure preserves valid state");
  restart();
  clock_at(TIME_BYTES, 7, 1, "incomplete stereo frame rounds down");
  clock_at(TIME_BYTES, 8, 2, "complete stereo frame advances");
  restart();
  clock_at(TIME_MS, 10, 480, "meter cursor in milliseconds");
  auto block = std::make_unique<Block>();
  block->start = 480; block->data.resize(16);
  const std::int16_t pairs[] = {8192, 0, 16384, 0, 8192, 0, 0, 0};
  std::memcpy(block->data.data(), pairs, sizeof(pairs));
  blocks.push_back(std::move(block));
  expect(std::strcmp(air_genesis_audio("levels", ""), "0.500000 0.000000") == 0,
         "post-mix meters use the converted sample cursor");
  clock_at(TIME_BYTES, 1936, 484, "meter cursor switches to bytes");
  expect(std::strcmp(air_genesis_audio("levels", ""), "0.000000 0.000000") == 0,
         "converted meter cursor leaves old PCM behind");
  restart();
  clock_at(TIME_SAMPLES, 0, 0, "restart clears counter epochs");
  device = nullptr;
  expect(std::strstr(air_genesis_audio("clock", ""), "[GA_AUDIO_CLOSED]") != nullptr,
         "closed device retains coded refusal");
  std::printf("Native audio clock: %u ABI checks, sample/byte/ms positions, rollover, jitter, unit changes, meter cursor and coded recovery passed\n", checks);
  return 0;
}
