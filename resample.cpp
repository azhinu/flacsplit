/* Simple linear resampler for downsampling audio
 * Copyright (c) 2026
 *
 * Permission to use, copy, modify, and/or distribute this software for any
 * purpose with or without fee is hereby granted, provided that the above
 * copyright notice and this permission notice appear in all copies.
 */

#include "resample.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace flacsplit {

Resampler::Resampler(int32_t input_rate, int32_t output_rate, int channels)
    : _input_rate(input_rate),
      _output_rate(output_rate),
      _channels(channels),
      _ratio(static_cast<double>(input_rate) / output_rate),
      _position(0.0),
      _last_samples(channels, 0) {
	
	if (output_rate > input_rate) {
		throw std::invalid_argument(
		    "upsampling not supported, only downsampling");
	}
	if (input_rate <= 0 || output_rate <= 0 || channels <= 0) {
		throw std::invalid_argument("invalid resampler parameters");
	}
}

Frame Resampler::resample(const Frame &input) {
	if (input.channels != _channels) {
		throw std::invalid_argument("channel count mismatch");
	}
	
	// Calculate exact output sample count
	int64_t output_samples = static_cast<int64_t>(
	    std::ceil((input.samples + _position) / _ratio));
	
	// Allocate buffer for non-interleaved output (channels * samples)
	_buffer.resize(output_samples * _channels);
	
	// Process each output sample
	for (int64_t out_idx = 0; out_idx < output_samples; out_idx++) {
		// Position in input corresponding to this output sample
		double in_pos = out_idx * _ratio - _position;
		
		// Integer and fractional parts
		int64_t in_idx = static_cast<int64_t>(std::floor(in_pos));
		double frac = in_pos - in_idx;
		
		// Interpolate each channel
		for (int ch = 0; ch < _channels; ch++) {
			int32_t s0, s1;
			
			// Get samples for interpolation
			if (in_idx < 0) {
				s0 = _last_samples[ch];
			} else if (in_idx >= input.samples) {
				s0 = input.data[ch][input.samples - 1];
			} else {
				s0 = input.data[ch][in_idx];
			}
			
			if (in_idx + 1 < 0) {
				s1 = _last_samples[ch];
			} else if (in_idx + 1 >= input.samples) {
				s1 = input.data[ch][input.samples - 1];
			} else {
				s1 = input.data[ch][in_idx + 1];
			}
			
			// Linear interpolation - store non-interleaved
			int32_t sample = static_cast<int32_t>(
			    s0 * (1.0 - frac) + s1 * frac);
			_buffer[ch * output_samples + out_idx] = sample;
		}
	}
	
	// Update position for next frame
	_position = (input.samples + _position) - output_samples * _ratio;
	
	// Save last samples for next frame
	for (int ch = 0; ch < _channels; ch++) {
		_last_samples[ch] = input.data[ch][input.samples - 1];
	}
	
	// Setup non-interleaved channel pointers
	_channel_ptrs.resize(_channels);
	for (int ch = 0; ch < _channels; ch++) {
		_channel_ptrs[ch] = _buffer.data() + ch * output_samples;
	}
	
	Frame output;
	output.data = _channel_ptrs.data();
	output.bits_per_sample = input.bits_per_sample;
	output.channels = _channels;
	output.samples = output_samples;
	output.rate = _output_rate;
	
	return output;
}

} // namespace flacsplit
