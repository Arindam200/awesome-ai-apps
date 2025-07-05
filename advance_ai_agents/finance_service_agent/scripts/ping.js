const args = process.argv.slice(2);

if (args.length < 1) {
    console.error("Usage: node ping.js <backend-url>");
    process.exit(1);
}

const BACKEND_URL = args[0];

async function pingBackend() {
    try {
        const response = await fetch(BACKEND_URL, { method: "GET" });
        if (response.ok) {
            console.log("Ping successful at", new Date().toLocaleTimeString());
        } else {
            console.error("Ping failed with status:", response.status);
        }
    } catch (error) {
        console.error("Ping error:", error);
    }
}

// Function call
pingBackend();