import NextAuth from "next-auth";
import MicrosoftEntraID from "next-auth/providers/microsoft-entra-id";
import Credentials from "next-auth/providers/credentials";

const providers = [];

if (process.env.CLIENT_ID && process.env.CLIENT_SECRET && process.env.TENANT_ID) {
  providers.push(
    MicrosoftEntraID({
      clientId: process.env.CLIENT_ID,
      clientSecret: process.env.CLIENT_SECRET,
      issuer: `https://login.microsoftonline.com/${process.env.TENANT_ID}/v2.0`,
    })
  );
}

if (process.env.NODE_ENV !== "production") {
  providers.push(
    Credentials({
      id: "dev-login",
      name: "Dev Login",
      credentials: { email: { label: "Email", type: "email" } },
      async authorize(credentials) {
        const email = credentials?.email as string | undefined;
        if (!email) return null;
        return { id: email, email, name: email.split("@")[0] };
      },
    })
  );
}

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers,
  callbacks: {
    async session({ session, token }) {
      if (token.email) session.user.email = token.email;
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
});
