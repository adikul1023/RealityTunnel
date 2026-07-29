process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';
async function run() {
    const res = await fetch("https://api.stealthy.co.in/api/admin/billing/provisioning?limit=1000", {
        headers: { Authorization: "Bearer superadmin" }
    });
    const data = await res.json();
    for (const p of data.items) {
        try {
            await fetch(`https://api.stealthy.co.in/api/admin/billing/provisioning/${p.id}/sync`, {
                method: "POST",
                headers: { Authorization: "Bearer superadmin" }
            });
            console.log(`Synced ${p.id}`);
        } catch (e) {
            console.log(`Failed ${p.id}`, e.message);
        }
    }
}
run();
