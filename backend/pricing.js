function calculateFare(distanceKm) {
  return {
    uber: Math.round((50 + distanceKm * 12) * 1.2),
    ola: Math.round(40 + distanceKm * 11),
    rapido: Math.round(25 + distanceKm * 8),
  };
}

module.exports = calculateFare;
