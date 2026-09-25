export type GroupMember = {
  id: string;
  name: string;
  color: string;
  joinedAt: string;
};

export type GroupMessage = {
  id: string;
  memberId: string;
  name: string;
  color: string;
  text: string;
  at: string;
};

export type GroupRoom = {
  code: string;
  name: string;
  createdAt: string;
  members: GroupMember[];
  messages: GroupMessage[];
};

export type GroupSummary = Pick<GroupRoom, 'code' | 'name' | 'createdAt'> & {
  memberCount: number;
};
