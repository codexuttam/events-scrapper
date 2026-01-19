const express = require("express");
const axios = require("axios");
const http = require("http");
const calculateFare = require("./pricing");

const router = express.Router();

async function getDistance(start, end) {
  const url = `http://router.project-osrm.org/route/v1/driving/${start.lon},${start.lat};${end.lon},${end.lat}?overview=false`;

  const agent = new http.Agent({
    family: 4, // ⭐ FORCE IPv4 (THIS IS THE KEY)
  });

  const res = await axios.get(url, {
    httpAgent: agent,
    timeout: 10000,
  });

  if (!res.data || !res.data.routes || res.data.routes.length === 0) {
    throw new Error("OSRM returned no routes");
  }

  return res.data.routes[0].distance / 1000;
}



router.post("/compare", async (req, res) => {
  try {
    const { pickup, destination } = req.body;

    // pickup and destination MUST be [lon, lat]
    if (
      !pickup ||
      !destination ||
      !Array.isArray(pickup) ||
      !Array.isArray(destination)
    ) {
      return res.status(400).json({
        error: "Invalid or missing coordinates",
      });
    }

    const start = { lon: pickup[0], lat: pickup[1] };
    const end = { lon: destination[0], lat: destination[1] };

    const distanceKm = await getDistance(start, end);
    const fares = calculateFare(distanceKm);

    res.json({
      distanceKm: distanceKm.toFixed(2),
      fares,
    });
  }   catch (err) {
  console.error("COMPARE ERROR FULL:", err);
  res.status(500).json({
    error: "Distance service failed",
  });
}


  
});

module.exports = router;
