import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import { getMe, getRegisteredUsers, getBusinessUnits } from "@/lib/api";
import Nav from "@/components/nav";
import AdminClient from "./admin-client";

export default async function AdminPage() {
  const session = await auth();
  if (!session?.user?.email) redirect("/login");

  const upn = session.user.email;
  const me = await getMe(upn).catch(() => null);

  if (!me) redirect("/");          // not registered at all
  if (!me.is_admin) redirect("/"); // registered but not admin

  const [users, businessUnits] = await Promise.all([
    getRegisteredUsers(upn).catch(() => []),
    getBusinessUnits(upn).catch(() => []),
  ]);

  return (
    <>
      <Nav userEmail={upn} isAdmin={true} />
      <AdminClient initialUsers={users} businessUnits={businessUnits} callerUpn={upn} />
    </>
  );
}
