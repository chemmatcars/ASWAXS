from scipy.integrate import odeint
from scipy.interpolate import interp1d
from lmfit import Parameters, minimize, fit_report
import copy
from scipy.optimize import leastsq


def find_edges(img, roi=None, threshhold=0.6, tip=0.77, mag_line=50, iplot=0):
    """
    Find the edge of the drop in a particular region of interest of the image
    tip=dimension of the tip in cm
    """
    if iplot != 0:
        figure(figsize=(10, 10))
        imshow(img)
    img = average(img, 2)
    mag = tip / (argmax(diff(img[mag_line, :])) - argmin(diff(img[mag_line, :])))
    if roi == None:
        pdx = diff(img, axis=0)
        pdy = diff(img, axis=1)
    else:
        if iplot != 0:
            axhline(mag_line, color='blue')
            axvline(roi[0], color='red')
            axvline(roi[2], color='red')
            axhline(roi[1], color='red')
            axhline(roi[3], color='red')
        pdx = diff(img[roi[1]:roi[3], roi[0]:roi[2]], axis=0)
        pdy = diff(img[roi[1]:roi[3], roi[0]:roi[2]], axis=1)
    edges = sqrt(pdx[:, :-1] ** 2 + pdy[:-1, :] ** 2)
    line1 = argwhere(edges > threshhold)
    if roi == None:
        x = line1[:, 1]
        y = line1[:, 0]
    else:
        x = line1[:, 1] + roi[0]
        y = line1[:, 0] + roi[1]
    if iplot != 0:
        plot(x, y, 'r.', markersize=1)
        axvline(mean(x), color='green')
        xticks([])
        yticks([])
        axes().set_aspect('equal')
    return (x - mean(x)) * mag, (-y + max(y)) * mag, mean(x), max(y), mag


def find_edges1(img, roi=None, sigma=10, tip=0.077, mag_line=50, iplot=0):
    """
    Find the edges of the drop in a particular region of interest of the image using scikit-image
    tip=dimension of the tip in cm
    sigma=width of gaussian filter
    """
    if iplot != 0:
        figure(figsize=(10, 10))
        imshow(img)
    img = average(img, axis=2)
    mag = tip / (argmax(diff(img[mag_line, :])) - argmin(diff(img[mag_line, :])))
    if roi != None:
        if iplot != 0:
            axhline(mag_line, color='blue')
            axvline(roi[0], color='red')
            axvline(roi[2], color='red')
            axhline(roi[1], color='red')
            axhline(roi[3], color='red')
        img = img[0:roi[3], roi[0]:roi[2]]
    ftimg = feature.canny(img, sigma=sigma)
    pos = argwhere(ftimg)
    xt = pos[:, 1]
    yt = pos[:, 0]
    rg = argwhere(yt > roi[1])
    x = xt[rg].transpose()[0]
    y = yt[rg].transpose()[0]
    if iplot != 0:
        axhline(mag_line, color='blue')
        axvline(roi[0], color='red')
        axvline(roi[2], color='red')
        axhline(roi[1], color='red')
        axhline(roi[3], color='red')
    if roi != None:
        x = x + roi[0]
        y = y
    if iplot != 0:
        plot(x, y, 'r.', markersize=1)
        axvline(mean(x), color='green')
        xticks([])
        yticks([])
        axes().set_aspect('equal')
    return (x - mean(x)) * mag, (-y + max(y)) * mag, mean(x), max(y), mag


def drop(xzt, s, b, c):
    x, z, t = xzt  # tuple unpacking
    if x == 0:
        sin0 = 1.0
    else:
        sin0 = sin(t) / x
    return [cos(t), sin(t), b + c * z - sin0]


def calc_profile(x, y, Npoints=1000):
    """
    Compute the profile of a drop with x and y being the co-ordinates extracted from image
    """
    xp, yp = x[argwhere(x >= 0).transpose()][0], y[argwhere(x >= 0).transpose()][0]
    xm, ym = x[argwhere(x < 0).transpose()][0], y[argwhere(x < 0).transpose()][0]
    xp, yp = xp[argsort(yp)], yp[argsort(yp)]
    xm, ym = xm[argsort(ym)], ym[argsort(ym)]
    xp = insert(xp, 0, 0.0);
    yp = insert(yp, 0, 0.0)
    xm = insert(xm, 0, 0.0);
    ym = insert(ym, 0, 0.0)
    fp = interp1d(yp, xp)
    y1p = linspace(yp[0] + 0.00001, yp[-1], Npoints)
    x1p = fp(y1p)
    fm = interp1d(ym, xm)
    y1m = linspace(ym[0] + 0.00001, ym[-1], Npoints)
    x1m = fm(y1m)
    spmax = sum(sqrt(diff(y1p) ** 2 + diff(x1p) ** 2))
    smmax = sum(sqrt(diff(y1m) ** 2 + diff(x1m) ** 2))
    sp = linspace(0, spmax + 0.1, Npoints)
    sm = linspace(0, smmax + 0.1, Npoints)
    return x1p, y1p, x1m, y1m, sp, sm


def gen_profile(x1p, y1p, x1m, y1m, sp, sm, b, rho1, rho2, gam, Npoints=100, iplot=0):
    """
    rho1 and rho2 are density of subphase and the drop solution in g/cm^3
    gam=interfacial tension of the drop in mN/m
    """
    c = -(rho2 - rho1) * 980.0 / gam
    xz0 = [0.0, 0.0, 0.0]
    ygp = odeint(drop, xz0, sp, args=(b, c))
    ygm = odeint(drop, xz0, sm, args=(b, c))
    xgp, ygp, thetagp = ygp.T
    xgm, ygm, thetagm = ygm.T
    xgm = -xgm
    fp = interp1d(ygp, xgp)
    fm = interp1d(ygm, xgm)
    xp = fp(y1p)
    xm = fm(y1m)
    vol = pi * sum(xp ** 2) * (y1p[1] - y1p[0])
    yp = y1p
    ym = y1m
    if iplot != 0:
        plot(xp, yp, 'r-')
        plot(xm, ym, 'r-')
        plot(x1p, y1p, 'b-')
        plot(x1m, y1m, 'b-')
    return x1p, y1p, x1m, y1m, xp, yp, xm, ym, vol


def residual(params, x1p, y1p, x1m, y1m, sp, sm, b, rho1, rho2, Npoints):
    """
    Computes the residual between the data and calculated drop profile from Laplace's equation
    """
    b = params['b'].value
    gam = params['gam'].value
    x0, y0 = params['x0'].value, params['y0'].value
    alf = params['alf'].value
    xp, yp, xm, ym, xgp, ygp, xgm, ygm, vol = gen_profile(x1p, y1p, x1m, y1m, sp, sm, b, rho1, rho2, gam,
                                                          Npoints=Npoints, iplot=0)
    return append(sqrt((xp - xgp) ** 2 + (yp - ygp) ** 2), sqrt((xm - xgm) ** 2 + (ym - ygm) ** 2))


def res_curve(par, x, y):
    b, x0, y0 = par
    R = 2.0 / b
    return (y - (y0 + R - sqrt(R ** 2 - (x - x0) ** 2)))


def profile_fit(x, y, rho1, rho2, gam, xo, yo, mag, Npoints=100, iprint=0, iplot=0):
    """
    Fitting the pendent drop profile to Laplaces equaiton
    """
    xc = x[argwhere(y < 0.30 * max(y))].transpose()[0]
    yc = y[argwhere(y < 0.30 * max(y))].transpose()[0]
    res = leastsq(res_curve, (2.0 / max(x), 0.0, 0.0), args=(xc, yc), maxfev=10000)
    par = res[0]
    b, x0, y0 = par
    ycg = yc - res_curve(par, xc, yc)
    params = Parameters()
    params.add('b', value=b, min=10.0, max=40.0, vary=True)
    params.add('gam', value=gam, min=20.0, max=100.0, vary=True)
    params.add('x0', value=x0, min=-0.01, max=0.01, vary=True)
    params.add('y0', value=y0, min=-0.01, max=0.01, vary=True)
    params.add('alf', value=0.0, min=-0.1, max=0.1, vary=False)
    x1p, y1p, x1m, y1m, sp, sm = calc_profile(x, y, Npoints=Npoints)
    out = minimize(residual, params, args=(x1p, y1p, x1m, y1m, sp, sm, b, rho1, rho2, Npoints))
    gam = params['gam'].value
    b = params['b'].value
    x0, y0 = params['x0'].value, params['y0'].value
    alf = params['alf'].value
    xp, yp, xm, ym, xgp, ygp, xgm, ygm, vol = gen_profile(x1p, y1p, x1m, y1m, sp, sm, b, rho1, rho2, gam,
                                                          Npoints=Npoints, iplot=0)
    # plot(out.residual)
    if iprint != 0:
        # print out.message
        # print out.nfev
        # print (fit_report(params))
        print('gam=%.2f +/-%.3f' % (params['gam'].value, params['gam'].stderr))
        print('Vol=%.3f ul' % (vol * 1000.0))
        print('b=%.2f +/-%.3f' % (params['b'].value, params['b'].stderr))
        print('(x0, y0)=(%.4f,%.4f)' % (params['x0'].value, params['y0'].value))
        print('alf=%.2f +/- %.3f' % (params['alf'].value, params['b'].stderr))
    if iplot != 0:
        # figure(figsize=(8,8))
        xgp = (xgp) * cos(alf) + (ygp) * sin(alf) + x0
        ygp = -(xgp) * sin(alf) + (ygp) * cos(alf) + y0
        xgm = (xgm) * cos(alf) + (ygm) * sin(alf) + x0
        ygm = -(xgm) * sin(alf) + (ygm) * cos(alf) + y0
        plot(xp / mag + xo, -yp / mag + yo, 'r-', lw=4)
        plot(xm / mag + xo, -yp / mag + yo, 'r-', lw=4)
        plot(xgp / mag + xo, -ygp / mag + yo, 'b-', lw=4)
        plot(xgm / mag + xo, -ygp / mag + yo, 'b-', lw=4)
        axes().set_aspect('equal')
    return vol * 1000, gam