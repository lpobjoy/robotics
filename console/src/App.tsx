import { useState } from "react";
import "./App.css";
import { AuditTrail } from "./components/AuditTrail";
import { EscalationQueue } from "./components/EscalationQueue";
import { MissionStatus } from "./components/MissionStatus";
import { WorkOrdersTable } from "./components/WorkOrdersTable";

function App() {
  const [selectedWorkOrderId, setSelectedWorkOrderId] = useState<number | null>(null);

  return (
    <div className="app">
      <header>
        <h1>robot-router console</h1>
        <p className="muted">
          Operator UI over a portfolio demo -- not a product. See CLAUDE.md section 4.8.
        </p>
      </header>

      <main>
        <WorkOrdersTable selectedWorkOrderId={selectedWorkOrderId} onSelect={setSelectedWorkOrderId} />
        <MissionStatus workOrderId={selectedWorkOrderId} />
        <EscalationQueue />
        <AuditTrail workOrderId={selectedWorkOrderId} />
      </main>
    </div>
  );
}

export default App;
