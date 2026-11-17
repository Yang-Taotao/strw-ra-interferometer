import numpy as np
import astropy.units as u
import astropy.constants as c
from rich.progress import track

# Helper functions for generating images
def pixel_brightness(acm_single_pol, l, m, uv, frequency):
    a = acm_single_pol.astype(np.complex64)
    n = a.shape[0]
    uv_l = uv.astype(np.float32)
    uv_l = (uv_l * frequency/c.c).decompose()
    ll = l.to(u.rad).value
    mm = m.to(u.rad).value
    mask = np.ones((n, n), dtype=np.float32)
    mask -= np.diag(np.ones(n, dtype=np.float32)) # remove auto-correlations
    num_vis = mask.sum()
    brightness = (a*mask*np.exp(2j*np.pi*(uv_l[...,0]*ll + uv_l[...,1]*mm))).real.sum()
    return brightness/num_vis


def make_image(acm, num_pix, uv, frequency,
               l_range=(1.0, -1.0),
               m_range=(-1.0, 1.0)):

    img = np.zeros((num_pix, num_pix), dtype=np.float32)

    l_coor = np.linspace(*l_range, num_pix) * u.rad
    m_coor = np.linspace(*m_range, num_pix) * u.rad

    # Loop over image pixels
    for m_ix, m in enumerate(track(m_coor, description="Generating image")):

        for l_ix, l in enumerate(l_coor):

            # Calculate brightness for every FFT block
            brightness = 0

            for b in range(acm.shape[0]):

                brightness += pixel_brightness(acm[b], l, m, uv[b], frequency)

            # Average over the integration
            img[m_ix, l_ix] = brightness / acm.shape[0]

    pixel_sep = m_coor[1] - m_coor[0]
    half = pixel_sep.to_value(u.rad) / 2

    img_extent = (l_coor[0].value - half, l_coor[-1].value + half, m_coor[0].value - half, m_coor[-1].value + half)

    return img, img_extent