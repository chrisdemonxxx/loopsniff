import Link from "next/link";
import { FileQuestion } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-950 p-4">
      <div className="text-center max-w-md mx-auto">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gray-800">
          <FileQuestion className="h-7 w-7 text-gray-400" />
        </div>
        <h2 className="text-xl font-semibold text-white mb-2">
          Page Not Found
        </h2>
        <p className="text-gray-400 text-sm mb-6">
          The page you&apos;re looking for doesn&apos;t exist or has been moved.
        </p>
        <Link
          href="/dashboard"
          className="inline-flex items-center justify-center rounded-md border border-gray-700 bg-gray-900 px-4 py-2 text-sm font-medium text-gray-200 hover:bg-gray-800"
        >
          Go to Dashboard
        </Link>
      </div>
    </div>
  );
}
