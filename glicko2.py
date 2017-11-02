# coding=utf-8
# refer to http://www.glicko.net/glicko/glicko2.pdf

import math

class Player:
	_tau = 1
	_epsilon = 0.000001

	def __init__(self, rating = 1500, rd = 350, vol = 0.06):
		self.rating = rating
		self.rd = rd
		self.vol = vol

	def _rating_to_glicko2(self, r):
		return (r - 1500) / 173.7178

	def _rating_to_glicko(self, mu):
		return (mu * 173.7178) + 1500

	def _rd_to_glicko2(self, RD):
		return RD / 173.7178

	def _rd_to_glicko(self, phi):
		return phi * 173.7178

	def update_player(self, opponents):
		# players who did not compete need fewer calculations
		if not opponents:
			sigma = self.vol
			phi = self._rd_to_glicko2(self.rd)
			phi_prime = math.sqrt(phi**2 + sigma**2)
			self.rd = self._rd_to_glicko(phi_prime)
			return

		tau = self._tau
		sigma = self.vol
		g = lambda phi: 1 / math.sqrt(1 + 3*phi**2 / math.pi**2)
		E = lambda mu, mu2, phi2: 1 / (1 + math.exp(-1 * g(phi2) * (mu - mu2)))

		# step 2
		mu = self._rating_to_glicko2(self.rating)
		phi = self._rd_to_glicko2(self.rd)

		# steps 3 and 4
		v_sum = 0
		delta_sum = 0
		for win, rating, rd in opponents:
			mu_j = self._rating_to_glicko2(rating)
			phi_j = self._rd_to_glicko2(rd)
			s_j = 1 if win else 0

			_E = E(mu, mu_j, phi_j)
			_g = g(phi_j)

			v_sum += _g**2 * _E * (1 - _E)
			delta_sum += _g * (s_j - _E)

		v = 1/v_sum
		delta = v*delta_sum

		# step 5.1
		a = math.log(sigma**2)
		epsilon = self._epsilon
		f = lambda x: (math.exp(x) * (delta**2 - phi**2 - v - math.exp(x)) / (2 * (phi**2 + v + math.exp(x))**2)) - (x-a)/tau**2

		# step 5.2
		A = a
		if delta**2 > phi**2 + v:
			B = math.log(delta**2 - phi**2 - v)
		else:
			B = a - tau
			while f(B) < 0:
				B += tau

		# step 5.3
		f_A = f(A)
		f_B = f(B)

		# step 5.4
		while abs(B - A) > epsilon:
			C = A + (A - B)*f_A / (f_B - f_A)
			f_C = f(C)
			if f_C - f_B < 0:
				A = B
				f_A = f_B
			else:
				f_A /= 2
			B = C
			f_B = f_C

		# step 5.5
		sigma_prime = math.exp(A/2)

		# step 6
		phi_star = math.sqrt(phi**2 + sigma_prime**2)

		# step 7
		phi_prime = 1 / math.sqrt(1/phi_star**2 + 1/v)
		mu_prime = mu + phi_prime * delta_sum

		# step 8
		self.rating = self._rating_to_glicko(mu_prime)
		self.rd = self._rd_to_glicko(phi_prime)

	def __repr__(self):
	  return "R:\t" + str(self.rating) + "\nRD:\t" + str(self.rd) + "\nVol:\t" + str(self.vol)

	def __str__(self):
	  return self.__repr__()
