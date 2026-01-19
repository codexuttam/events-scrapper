import { useState } from "react";

export default function App() {
  const [pickup, setPickup] = useState("");
  const [destination, setDestination] = useState("");
  const [pickupCoords, setPickupCoords] = useState(null);
  const [destCoords, setDestCoords] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function getCoords(place, setter) {
    const res = await fetch(
      `https://photon.komoot.io/api/?q=${encodeURIComponent(
        place
      )}&limit=1`
    );
    const data = await res.json();

    if (!data.features || data.features.length === 0) {
      throw new Error("Place not found");
    }

    const [lon, lat] = data.features[0].geometry.coordinates;
    setter([lon, lat]);
  }

  async function compareRides() {
    try {
      setError("");
      setLoading(true);
      setResult(null);

      await getCoords(pickup, setPickupCoords);
      await getCoords(destination, setDestCoords);

      const res = await fetch("http://localhost:5000/api/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pickup: pickupCoords,
          destination: destCoords,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Something went wrong");

      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-100 to-gray-300 flex items-center justify-center px-4">
      <div className="bg-white w-full max-w-md rounded-2xl shadow-2xl p-8">
        <h1 className="text-2xl font-extrabold text-center mb-6">
          Ride Price Comparator 🚕
        </h1>

        <input
          className="w-full mb-3 p-3 border rounded"
          placeholder="Pickup location"
          value={pickup}
          onChange={(e) => setPickup(e.target.value)}
        />

        <input
          className="w-full mb-4 p-3 border rounded"
          placeholder="Destination"
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
        />

        <button
          onClick={compareRides}
          disabled={loading}
          className="w-full bg-indigo-600 text-white py-3 rounded-lg hover:bg-indigo-700 font-semibold"
        >
          {loading ? "Calculating..." : "Compare Prices"}
        </button>

        {error && (
          <p className="text-red-600 text-sm mt-3 text-center">{error}</p>
        )}

        {result && (
          <div className="mt-6 space-y-2">
            <p className="text-center text-gray-600">
              Distance: {result.distanceKm} km
            </p>

            <div className="border p-3 rounded flex justify-between">
              <span>Uber</span>
              <span>₹{result.fares.uber}</span>
            </div>

            <div className="border p-3 rounded flex justify-between">
              <span>Ola</span>
              <span>₹{result.fares.ola}</span>
            </div>

            <div className="border p-3 rounded flex justify-between font-bold text-green-600">
              <span>Rapido</span>
              <span>₹{result.fares.rapido}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
