/* Simple linear resampler for downsampling audio
 * Copyright (c) 2026
 *
 * Permission to use, copy, modify, and/or distribute this software for any
 * purpose with or without fee is hereby granted, provided that the above
 * copyright notice and this permission notice appear in all copies.
 */

#ifndef RESAMPLE_HPP
#define RESAMPLE_HPP

#include <cstdint>
#include <memory>
#include <vector>

#include "transcode.hpp"

namespace flacsplit {

class Resampler {
public:
	Resampler(int32_t input_rate, int32_t output_rate, int channels);
	
	// Resample a frame. Returns a new Frame with resampled data.
	// The caller owns the returned data and must free it.
	Frame resample(const Frame &input);
	
	int32_t output_rate() const { return _output_rate; }

private:
	int32_t _input_rate;
	int32_t _output_rate;
	int _channels;
	double _ratio;
	double _position;
	std::vector<int32_t> _last_samples;
	std::vector<int32_t> _buffer;
	std::vector<const int32_t *> _channel_ptrs;
};

} // namespace flacsplit

#endif // RESAMPLE_HPP
