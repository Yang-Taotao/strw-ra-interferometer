"""
Sample loss calculation utilities.
"""

import numpy as np
import tqdm
import matplotlib.pyplot as plt

data_1 = np.memmap("C:/Files/Leiden/A - Master/MSc jaar 2/Radio/Test_measurement_30-10/init_data_1", dtype=np.complex64)
data_2 = np.memmap("C:/Files/Leiden/A - Master/MSc jaar 2/Radio/Test_measurement_30-10/init_data_2", dtype=np.complex64)

import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import correlate

#Take the same number of samples from both recordings
N = 1000000
x = data_1[:N].copy()  
y = data_2[:N].copy()

#Function that removes the strongest tone from a signal
def remove_tone(s, half_width=100):
    """Zero the strongest spectral peak (and its mirror bin for real data)."""
    # Subtracting the mean first removes the DC offset, which would otherwise be the strongest "peak" at bin 0
    S = np.fft.fft(s - s.mean())

    # Index of the frequency bin with the largest magnitude
    k = np.argmax(np.abs(S))

    # Set that bin and its neighbours to zero. The tone is never perfectly
    # sharp (spectral leakage), so we remove +/- half_width bins around it.
    # max(..., 0) stops the slice index from going negative.
    S[max(k-half_width, 0):k+half_width+1] = 0

    out = np.fft.ifft(S).real
    return out 

#Normalized cross-correlation
def ncc(a, b):
    """Correlation of a and b, scaled so that identical signals give 1.0 at lag 0."""

    # Subtract the mean and divide by the standard deviation, so each signal
    # has mean 0 and variance 1.
    a = (a - a.mean()) / a.std()
    b = (b - b.mean()) / b.std()
    correlation = correlate(b, a, mode='full')
    return correlation

#Remove the tone from both signals, then correlate
xc, yc = remove_tone(x), remove_tone(y)

auto  = ncc(xc, xc)    #Should peak at 1.0 at lag 0, since it's the same signal
cross = ncc(xc, yc)    #If the signals are independent, there should be no peak at lag 0
lags  = np.arange(-N+1, N)   # lag axis matching

print("auto  lag 0:", auto[N-1].real)
print("cross lag 0:", cross[N-1].real)  
i = np.abs(cross).argmax()               
print("cross max:", np.abs(cross[i]), "at lag", lags[i])


fig, ax = plt.subplots(1, 1, figsize=(6, 4))

w = np.abs(lags) < 50   #zoom in on the region around lag 0
ax.plot(lags[w], auto[w].real, label='auto data1')
ax.plot(lags[w], cross[w].real, label='cross data1 with data2')
ax.set_title('zoom around lag 0'); ax.legend()
ax.set_xlabel('lag (samples)')
ax.set_ylabel('correlation coefficient')

plt.show()

def block_lags(ref, other, block=2**20, max_lag=2**18):
    out = []
    # iterate over blocks of the reference and other signals, compute cross-correlation, and find the lag with the maximum correlation
    for i in tqdm.tqdm(range(0, min(len(ref), len(other)) - block + 1, block)):
        # Compute the cross-correlation between the current blocks of the reference and other signals
        x, y = ref[i:i+block], other[i:i+block]
        # Use FFT to compute the cross-correlation efficiently
        c = np.fft.ifft(np.fft.fft(x, 2*block) * np.conj(np.fft.fft(y, 2*block)))
        # Keep only the relevant part of the cross-correlation and find the lag with the maximum correlation
        c = np.abs(np.concatenate([c[-max_lag:], c[:max_lag + 1]]))
        # Find the index of the maximum correlation and calculate the corresponding lag
        k = int(np.argmax(c))
        # Calculate the lag relative to the center of the cross-correlation array
        out.append((i, k - max_lag, (c[k] - np.median(c)) / c.std()))
    return np.array(out)   # (block start, lag, peak significance)

test = block_lags(data_1, data_2, block=2**20, max_lag=2**18)


plt.figure(figsize=(12, 6))
plt.subplot(2, 1, 1)
plt.plot(test[:, 0], test[:, 1], label='Lag (samples)')
plt.ylabel('Lag (samples)')
plt.subplot(2, 1, 2)
plt.plot(test[:, 0], test[:, 2], label='Peak significance', color='orange')
plt.ylabel('Peak significance')
plt.xlabel('Block start index')
plt.tight_layout()
plt.show()







