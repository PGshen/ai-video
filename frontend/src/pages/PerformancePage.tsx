import { useParams } from "react-router-dom";

export default function PerformancePage() {
  const { id } = useParams<{ id: string }>();
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">发布表现数据录入</h1>
      <p className="text-muted-foreground">TODO: PerformancePage — project: {id}</p>
    </div>
  );
}
