import { useParams } from "react-router-dom";

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">项目详情</h1>
      <p className="text-muted-foreground">TODO: ProjectDetailPage — id: {id}</p>
    </div>
  );
}
