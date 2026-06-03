import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import { getAllMeetings, getUpcomingMeetings, getMe, getHistoricalMeetings } from "@/lib/api";
import Nav from "@/components/nav";
import DashboardClient from "./dashboard-client";
import PendingAccess from "@/components/pending-access";

export default async function DashboardPage() {
  const session = await auth();
  if (!session?.user?.email) redirect("/login");

  const upn = session.user.email;

  // Check if the user is registered — unregistered domain users see the pending screen.
  const me = await getMe(upn).catch(() => null);
  if (!me) {
    return <PendingAccess userEmail={upn} />;
  }

  const [meetings, upcoming, historical] = await Promise.all([
    getAllMeetings(upn).catch(() => []),
    getUpcomingMeetings(upn).catch(() => []),
    getHistoricalMeetings(upn).catch(() => []),
  ]);

  return (
    <>
      <Nav userEmail={upn} isAdmin={me.is_admin} />
      <DashboardClient meetings={meetings} upcoming={upcoming} historical={historical} upn={upn} />
    </>
  );
}
